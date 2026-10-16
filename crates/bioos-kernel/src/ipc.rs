//! # BioOS Inter-Process Communication (IPC) & Lockless Ring Buffers
//! Standards: IEC 62304 Class C, DO-178C Level A
//! Wait-free, zero-allocation SPSC ring buffers for hard real-time threads.

use core::sync::atomic::{AtomicUsize, Ordering};

pub const RING_BUFFER_CAPACITY: usize = 32;

#[derive(Clone, Copy, Debug, Default)]
pub struct IpcMessage {
    pub msg_type: u16,
    pub source_engine: u8,
    pub target_engine: u8,
    pub payload_u64: u64,
    pub timestamp_ns: u64,
}

pub struct SpscRingBuffer {
    buffer: [IpcMessage; RING_BUFFER_CAPACITY],
    head: AtomicUsize, // Written by Producer
    tail: AtomicUsize, // Written by Consumer
}

impl Default for SpscRingBuffer {
    fn default() -> Self {
        Self::new()
    }
}

impl SpscRingBuffer {
    pub const fn new() -> Self {
        Self {
            buffer: [IpcMessage {
                msg_type: 0,
                source_engine: 0,
                target_engine: 0,
                payload_u64: 0,
                timestamp_ns: 0,
            }; RING_BUFFER_CAPACITY],
            head: AtomicUsize::new(0),
            tail: AtomicUsize::new(0),
        }
    }

    /// Enqueues a message into the ring buffer (wait-free, O(1)).
    /// Returns true if enqueued, false if buffer is full.
    pub fn push(&mut self, msg: IpcMessage) -> bool {
        let head = self.head.load(Ordering::Relaxed);
        let tail = self.tail.load(Ordering::Acquire);

        let next_head = (head + 1) % RING_BUFFER_CAPACITY;
        if next_head == tail {
            return false; // Buffer Full
        }

        self.buffer[head] = msg;
        self.head.store(next_head, Ordering::Release);
        true
    }

    /// Dequeues a message from the ring buffer (wait-free, O(1)).
    /// Returns Some(msg) or None if buffer is empty.
    pub fn pop(&mut self) -> Option<IpcMessage> {
        let tail = self.tail.load(Ordering::Relaxed);
        let head = self.head.load(Ordering::Acquire);

        if head == tail {
            return None; // Buffer Empty
        }

        let msg = self.buffer[tail];
        let next_tail = (tail + 1) % RING_BUFFER_CAPACITY;
        self.tail.store(next_tail, Ordering::Release);
        Some(msg)
    }

    pub fn is_empty(&self) -> bool {
        self.head.load(Ordering::Relaxed) == self.tail.load(Ordering::Relaxed)
    }

    pub fn len(&self) -> usize {
        let head = self.head.load(Ordering::Relaxed);
        let tail = self.tail.load(Ordering::Relaxed);
        if head >= tail {
            head - tail
        } else {
            RING_BUFFER_CAPACITY - (tail - head)
        }
    }
}
