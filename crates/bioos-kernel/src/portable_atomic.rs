//! # BioOS Portable 64-bit Atomic Cell
//!
//! Cortex-M (thumbv7em) is a 32-bit target with NO native 64-bit atomics;
//! `core::sync::atomic::AtomicU64` does not exist there. This module provides
//! `PortableAtomicU64` with three compile-time variants:
//!
//! * 64-bit targets (host x86_64, MI300X): true `AtomicU64` — wait-free.
//! * 32-bit targets without `target-stm32`: plain spinlock cell (fallback).
//! * 32-bit targets WITH `target-stm32` (Cortex-M4F on-target): INTERRUPT-
//!   MASKED access via `cortex_m::interrupt::free` — closes the documented
//!   priority-inversion constraint (P2 design doc section 3): whoever runs
//!   masks first, the other context is PENDED rather than spinning against
//!   it, so a main-loop holder can never deadlock an ISR. The mask covers
//!   the ENTIRE access (acquire + use + release), eliminating the
//!   unlock-ordering bug class entirely. Bounded cost: a few masked
//!   instructions per access; no ISR spins.
//!
//! Selection uses stable cfgs only (`target_pointer_width`, cargo features).

use core::sync::atomic::Ordering;

#[cfg(target_pointer_width = "64")]
use core::sync::atomic::AtomicU64;

#[cfg(all(target_pointer_width = "32", not(feature = "target-stm32")))]
use core::cell::UnsafeCell;
#[cfg(all(target_pointer_width = "32", not(feature = "target-stm32")))]
use core::sync::atomic::AtomicBool;

#[cfg(all(target_pointer_width = "32", feature = "target-stm32"))]
use core::cell::UnsafeCell;

/// 64-bit atomic cell portable across 64-bit and 32-bit (no 64-bit atomic) targets.
#[repr(transparent)]
pub struct PortableAtomicU64 {
    #[cfg(target_pointer_width = "64")]
    inner: AtomicU64,
    #[cfg(all(target_pointer_width = "32", not(feature = "target-stm32")))]
    inner: SpinCellU64,
    #[cfg(all(target_pointer_width = "32", feature = "target-stm32"))]
    inner: MaskedCellU64,
}

#[cfg(all(target_pointer_width = "32", not(feature = "target-stm32")))]
struct SpinCellU64 {
    lock: AtomicBool,
    value: UnsafeCell<u64>,
}

// Safety (plain spin fallback): the spinlock serializes all accesses.
#[cfg(all(target_pointer_width = "32", not(feature = "target-stm32")))]
unsafe impl Sync for SpinCellU64 {}

#[cfg(all(target_pointer_width = "32", not(feature = "target-stm32")))]
impl SpinCellU64 {
    const fn new(value: u64) -> Self {
        Self {
            lock: AtomicBool::new(false),
            value: UnsafeCell::new(value),
        }
    }

    #[inline]
    fn load(&self, _order: Ordering) -> u64 {
        self.lock();
        let v = unsafe { *self.value.get() };
        self.unlock();
        v
    }

    #[inline]
    fn store(&self, v: u64, _order: Ordering) {
        self.lock();
        unsafe { *self.value.get() = v };
        self.unlock();
    }

    #[inline]
    fn fetch_add(&self, v: u64, _order: Ordering) -> u64 {
        self.lock();
        let prev = unsafe { *self.value.get() };
        unsafe { *self.value.get() = prev.wrapping_add(v) };
        self.unlock();
        prev
    }

    #[inline]
    fn lock(&self) {
        while self.lock.swap(true, Ordering::Acquire) {
            core::hint::spin_loop();
        }
    }

    #[inline]
    fn unlock(&self) {
        self.lock.store(false, Ordering::Release);
    }
}

// On-target variant: interrupt-masked access (closes the ISR priority-
// inversion constraint; see module docs). The mask covers the ENTIRE access,
// so no unlock-ordering bug class exists and no ISR ever spins.
#[cfg(all(target_pointer_width = "32", feature = "target-stm32"))]
struct MaskedCellU64 {
    value: UnsafeCell<u64>,
}

// Safety (masked variant): cortex_m::interrupt::free masks all configurable
// interrupts for the whole access.
#[cfg(all(target_pointer_width = "32", feature = "target-stm32"))]
unsafe impl Sync for MaskedCellU64 {}

#[cfg(all(target_pointer_width = "32", feature = "target-stm32"))]
impl MaskedCellU64 {
    const fn new(value: u64) -> Self {
        Self {
            value: UnsafeCell::new(value),
        }
    }

    #[inline]
    fn load(&self, _order: Ordering) -> u64 {
        cortex_m::interrupt::free(|_| unsafe { *self.value.get() })
    }

    #[inline]
    fn store(&self, v: u64, _order: Ordering) {
        cortex_m::interrupt::free(|_| unsafe {
            *self.value.get() = v;
        });
    }

    #[inline]
    fn fetch_add(&self, v: u64, _order: Ordering) -> u64 {
        cortex_m::interrupt::free(|_| unsafe {
            let prev = *self.value.get();
            *self.value.get() = prev.wrapping_add(v);
            prev
        })
    }
}

impl PortableAtomicU64 {
    pub const fn new(value: u64) -> Self {
        Self {
            #[cfg(target_pointer_width = "64")]
            inner: AtomicU64::new(value),
            #[cfg(all(target_pointer_width = "32", not(feature = "target-stm32")))]
            inner: SpinCellU64::new(value),
            #[cfg(all(target_pointer_width = "32", feature = "target-stm32"))]
            inner: MaskedCellU64::new(value),
        }
    }

    #[inline]
    pub fn load(&self, order: Ordering) -> u64 {
        self.inner.load(order)
    }

    #[inline]
    pub fn store(&self, value: u64, order: Ordering) {
        self.inner.store(value, order)
    }

    #[inline]
    pub fn fetch_add(&self, value: u64, order: Ordering) -> u64 {
        self.inner.fetch_add(value, order)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_portable_atomic_u64_host_path() {
        let cell = PortableAtomicU64::new(1_000);
        assert_eq!(cell.load(Ordering::Relaxed), 1_000);
        cell.store(2_000, Ordering::Relaxed);
        assert_eq!(cell.fetch_add(5, Ordering::Relaxed), 2_000);
        assert_eq!(cell.load(Ordering::Relaxed), 2_005);
    }
}
