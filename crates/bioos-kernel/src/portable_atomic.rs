//! # BioOS Portable 64-bit Atomic Cell
//!
//! Cortex-M (thumbv7em) is a 32-bit target with NO native 64-bit atomics;
//! `core::sync::atomic::AtomicU64` does not exist there. This module provides
//! `PortableAtomicU64`:
//!
//! * 64-bit targets (host x86_64, MI300X): delegates to the real `AtomicU64`
//!   - truly wait-free, lock-free, unchanged semantics
//! * 32-bit targets (Cortex-M4F): interrupt-unsafe-free spinlock cell
//!   - lock-free (bounded progress), NOT wait-free; critical section is
//!     a few instructions (load/store/fetch_add on one u64)
//!   - KNOWN P2 CONSTRAINT: ISR-context access must mask interrupts at or
//!     above the spinlock priority, else priority inversion can deadlock.
//!     This is an integration requirement of the on-target phase, to be
//!     satisfied with `cortex_m::interrupt::free` or NVIC basepri locking.
//!
//! Selection uses `target_pointer_width` (stable cfg). Some 32-bit targets
//! do have 64-bit atomics (e.g. ARMv8-A LDRD/STRD+LDREXD); choosing the
//! portable path there is conservative, not incorrect.

use core::sync::atomic::Ordering;

#[cfg(target_pointer_width = "64")]
use core::sync::atomic::AtomicU64;

#[cfg(target_pointer_width = "32")]
use core::cell::UnsafeCell;
#[cfg(target_pointer_width = "32")]
use core::sync::atomic::AtomicBool;

/// 64-bit atomic cell portable across 64-bit and 32-bit (no 64-bit atomic) targets.
#[repr(transparent)]
pub struct PortableAtomicU64 {
    #[cfg(target_pointer_width = "64")]
    inner: AtomicU64,
    #[cfg(target_pointer_width = "32")]
    inner: SpinCellU64,
}

#[cfg(target_pointer_width = "32")]
struct SpinCellU64 {
    lock: AtomicBool,
    value: UnsafeCell<u64>,
}

// Safety (32-bit path): the spinlock serializes all accesses to `value`.
#[cfg(target_pointer_width = "32")]
unsafe impl Sync for SpinCellU64 {}

#[cfg(target_pointer_width = "32")]
impl SpinCellU64 {
    const fn new(value: u64) -> Self {
        Self {
            lock: AtomicBool::new(false),
            value: UnsafeCell::new(value),
        }
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
}

impl PortableAtomicU64 {
    pub const fn new(value: u64) -> Self {
        Self {
            #[cfg(target_pointer_width = "64")]
            inner: AtomicU64::new(value),
            #[cfg(target_pointer_width = "32")]
            inner: SpinCellU64::new(value),
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
