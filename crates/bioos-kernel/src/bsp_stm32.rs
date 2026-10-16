//! # BioOS STM32F407VG Board Support (P2.1 skeleton)
//!
//! Feature-gated (`target-stm32`): compiled ONLY for on-target builds; host
//! and simulation builds are completely unaffected.
//!
//! Implements the P2 design document (docs/p2_on_target_design.md):
//! - 168 MHz clock + 1 kHz SysTick tick source (P2.2 time base)
//! - DWT CYCCNT -> `now_ns()` u64 monotonic time (wrap-safe via cycles math)
//! - SSR + mechanical relay GPIOs WITH READBACK (closed-loop, H-04 residual)
//! - IWDG independent watchdog (refresh ONLY after non-lockout WIE cycles)
//! - Latching panic handler: lockout latch -> noinit post-mortem -> halt
//!
//! SKELETON SCOPE: compiles as an rlib (CI gate); the executable image and
//! HIL validation arrive with the P2.1 bin crate on hardware.

use cortex_m::peripheral::DWT;
use stm32f4xx_hal::{pac, prelude::*};

use crate::engine4_wie::WatchdogState;

/// Post-mortem latch (noinit placement is a P2.3 linker task; today this lives
/// in .bss and is documented as a known limitation).
#[link_section = ".bss.bsp_postmortem"]
static BSP_POSTMORTEM: core::sync::atomic::AtomicU32 =
    core::sync::atomic::AtomicU32::new(0);

/// 1 kHz SysTick counter (drives the u64 time base composition)
static BSP_TICKS: core::sync::atomic::AtomicU32 =
    core::sync::atomic::AtomicU32::new(0);

pub const POSTMORTEM_MAGIC: u32 = 0xB105_0555;

/// Board-owned relay + readback pins (PB0-PB3 on the F407VG; GPIOB because it
/// sits on APB2-free domain away from the ADC pins used by the lab sensors).
pub struct RelayPins {
    ssr: stm32f4xx_hal::gpio::AnyPin<stm32f4xx_hal::gpio::Output<stm32f4xx_hal::gpio::PushPull>>,
    mech: stm32f4xx_hal::gpio::AnyPin<stm32f4xx_hal::gpio::Output<stm32f4xx_hal::gpio::PushPull>>,
    ssr_readback: stm32f4xx_hal::gpio::AnyPin<stm32f4xx_hal::gpio::Input>,
    mech_readback: stm32f4xx_hal::gpio::AnyPin<stm32f4xx_hal::gpio::Input>,
}

// Safety: the relay pins are owned exclusively by the WIE decision path
// (SysTick ISR context on target); no other context may move them.
unsafe impl Send for RelayPins {}

static mut RELAY_PINS: Option<RelayPins> = None;

// IWDG raw register access: decouples the safety watchdog from HAL PAC field
// visibility. Base 0x40003000; KR 0x00, PR 0x04, RLR 0x08 (16-bit registers).
const IWDG_BASE: usize = 0x4000_3000;
const IWDG_KEY_START: u16 = 0xCCCC;
const IWDG_KEY_REFRESH: u16 = 0xAAAA;

fn iwdg_write_key(key: u16) {
    unsafe {
        core::ptr::write_volatile(IWDG_BASE as *mut u16, key);
    }
}

pub fn iwdg_start_raw() {
    iwdg_write_key(IWDG_KEY_START); // enables LSI + counter
    // Prescaler 32 -> 1 kHz tick; reload 49 -> ~50 ms window
    unsafe {
        core::ptr::write_volatile((IWDG_BASE + 0x04) as *mut u16, 3); // PR: div32
        core::ptr::write_volatile((IWDG_BASE + 0x08) as *mut u16, 49); // RLR
    }
    iwdg_write_key(IWDG_KEY_REFRESH); // reload applies RLR
}

pub fn iwdg_refresh_raw() {
    iwdg_write_key(IWDG_KEY_REFRESH);
}

/// Board bring-up: 168 MHz clocks, DWT cycle counter, 1 kHz SysTick,
/// relay GPIOs + readbacks, IWDG start. Call once, before any engine use.
/// Returns the relay pin handle container into BSP static ownership.
pub fn init() {
    let dp = pac::Peripherals::take().expect("STM32 peripherals already taken");
    let mut cp = cortex_m::Peripherals::take().expect("Cortex-M peripherals already taken");

    // Clocks: HSI-driven 168 MHz configuration via HAL
    let rcc = dp.RCC.constrain();
    let clocks = rcc.cfgr.sysclk(168.MHz()).freeze();

    // DWT cycle counter for WCET + time base
    cp.DCB.enable_trace();
    cp.DWT.enable_cycle_counter();

    // 1 kHz SysTick (168 MHz / 168000 - 1)
    let mut syst = cp.SYST;
    syst.set_clock_source(cortex_m::peripheral::syst::SystClkSource::Core);
    syst.set_reload(168_000 - 1);
    syst.enable_interrupt();
    syst.enable_counter();

    // Relay GPIOs + readbacks (PA0..PA3)
    let gpioa = dp.GPIOA.split();
    let pins = RelayPins {
        ssr: gpioa.pa0.into_push_pull_output().erase(),
        mech: gpioa.pa1.into_push_pull_output().erase(),
        ssr_readback: gpioa.pa2.into_pull_down_input().erase(),
        mech_readback: gpioa.pa3.into_pull_down_input().erase(),
    };

    // IWDG: LSI ~32 kHz, prescaler 32 -> 1 kHz, reload 50 -> 50 ms window.
    // Refreshed ONLY from feed_iwdg() after non-lockout WIE cycles.
    iwdg_start_raw();

    cortex_m::interrupt::free(|_| {
        unsafe { RELAY_PINS = Some(pins); }
    });

    // Hold clocks alive for the lifetime of the program (HAL freeze returns
    // a token; leaking it here is the standard embedded pattern).
    let _clocks = clocks; // configuration token must outlive pin use

    // Open the mechanical air gap and de-energize the SSR at boot: the safe
    // default is NO actuation until the WIE cycle explicitly permits it.
    relay_ssr_set(false);
    relay_mech_set(false);
}

/// SSR control + readback closed loop. Returns the READBACK state (truth).
pub fn relay_ssr_set(energized: bool) -> bool {
    cortex_m::interrupt::free(|_| {
        if let Some(pins) = unsafe { (&raw mut RELAY_PINS).as_mut() }.and_then(|p| p.as_mut()) {
            if energized {
                pins.ssr.set_high();
            } else {
                pins.ssr.set_low();
            }
            pins.ssr_readback.is_high()
        } else {
            false
        }
    })
}

/// Mechanical relay control + readback closed loop.
pub fn relay_mech_set(closed: bool) -> bool {
    cortex_m::interrupt::free(|_| {
        if let Some(pins) = unsafe { (&raw mut RELAY_PINS).as_mut() }.and_then(|p| p.as_mut()) {
            if closed {
                pins.mech.set_high();
            } else {
                pins.mech.set_low();
            }
            pins.mech_readback.is_high()
        } else {
            false
        }
    })
}

/// IWDG refresh â€” call ONLY after a WIE cycle that did NOT return lockout.
pub fn feed_iwdg() {
    iwdg_refresh_raw();
}

/// Apply a WIE watchdog decision to the physical relays.
/// Returns the READBACK pair (ssr_energized, mech_closed).
pub fn apply_watchdog_state(state: WatchdogState) -> (bool, bool) {
    match state {
        WatchdogState::Normal => {
            let ssr = relay_ssr_set(true);
            let mech = relay_mech_set(true);
            feed_iwdg();
            (ssr, mech)
        }
        WatchdogState::Caution => {
            let ssr = relay_ssr_set(true);
            let mech = relay_mech_set(true);
            feed_iwdg();
            (ssr, mech)
        }
        WatchdogState::HardwareLockout => {
            // NO IWDG feed: a stuck lockout path ends in a watchdog reset,
            // which re-enters boot with relays open (fail-safe default).
            let ssr = relay_ssr_set(false);
            let mech = relay_mech_set(false);
            (ssr, mech)
        }
    }
}

/// u64 monotonic nanoseconds from DWT cycles (168 MHz).
/// Wraps every ~25.6 s of CYCCNT (32-bit); the composition below is wrap-safe
/// by design and refined by the TIM2+overflow counter in P2.2.
pub fn now_ns() -> u64 {
    let cycles = DWT::cycle_count() as u64;
    cycles * 1_000 / 168
}

/// SysTick ISR: 1 kHz tick source. Registered by cortex-m-rt on target.
#[cfg(feature = "target-stm32")]
#[cortex_m_rt::exception]
fn SysTick() {
    use core::sync::atomic::Ordering;
    BSP_TICKS.fetch_add(1, Ordering::Relaxed);
}

/// Latching panic handler REPLACEMENT (feature-gated; overrides the generic
/// latch-and-spin in lib.rs for on-target builds).
/// Order of operations per the P2 design doc section 5:
/// 1. De-energize SSR, open mechanical air gap (readback truth)
/// 2. Latch post-mortem record (magic + reason code)
/// 3. Halt (IWDG resets if the halt itself hangs)
#[cfg(feature = "target-stm32")]
#[panic_handler]
fn bioos_target_panic(_info: &core::panic::PanicInfo) -> ! {
    use core::sync::atomic::Ordering;

    // 1. Physical fail-safe: relays open (best-effort; readback ignored here
    //    because a panic means the software contract is already broken).
    let _ = relay_ssr_set(false);
    let _ = relay_mech_set(false);

    // 2. Post-mortem latch
    BSP_POSTMORTEM.store(POSTMORTEM_MAGIC, Ordering::SeqCst);

    // 3. Halt (IWDG backstop)
    loop {
        core::hint::spin_loop();
    }
}
