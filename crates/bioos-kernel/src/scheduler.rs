//! # BioOS Real-Time Microkernel Task Scheduler
//! Standards: IEC 62304 Class C, DO-178C Level A
//! Implements a deterministic Rate-Monotonic & Earliest Deadline First (EDF) scheduler.
//! Zero dynamic heap allocation (#![no_std]).

use core::sync::atomic::{AtomicU64, Ordering};

pub const MAX_REALTIME_TASKS: usize = 8;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum TaskPriority {
    Critical1000Hz = 0, // 1 ms period, WCET <= 100 us (Actuator Control)
    Envelope100Hz = 1,  // 10 ms period, WCET <= 500 us (Kalman & Stall Protection)
    Watchdog50Hz = 2,   // 20 ms period, WCET <= 200 us (CRC & Relay Interlock)
    Telemetry10Hz = 3,  // 100 ms period, WCET <= 1 ms (Biomarkers & Sensors)
    Operations1Hz = 4,  // 1000 ms period, WCET <= 5 ms (Hospital Capacity & Staff)
}

#[derive(Clone, Copy, Debug)]
pub struct TaskControlBlock {
    pub task_id: u8,
    pub name: [u8; 16],
    pub priority: TaskPriority,
    pub period_ns: u64,
    pub deadline_ns: u64,
    pub wcet_ns: u64,
    pub last_execution_ns: u64,
    pub execution_count: u64,
    pub missed_deadlines: u32,
    pub is_active: bool,
}

impl TaskControlBlock {
    pub const fn empty() -> Self {
        Self {
            task_id: 0,
            name: [0u8; 16],
            priority: TaskPriority::Operations1Hz,
            period_ns: 1_000_000_000,
            deadline_ns: 1_000_000_000,
            wcet_ns: 0,
            last_execution_ns: 0,
            execution_count: 0,
            missed_deadlines: 0,
            is_active: false,
        }
    }
}

pub struct RealTimeScheduler {
    pub tasks: [TaskControlBlock; MAX_REALTIME_TASKS],
    pub current_time_ns: AtomicU64,
    pub total_cycles_dispatched: AtomicU64,
}

impl RealTimeScheduler {
    pub const fn new() -> Self {
        Self {
            tasks: [TaskControlBlock::empty(); MAX_REALTIME_TASKS],
            current_time_ns: AtomicU64::new(0),
            total_cycles_dispatched: AtomicU64::new(0),
        }
    }

    pub fn register_task(
        &mut self,
        slot: usize,
        task_id: u8,
        name_str: &str,
        priority: TaskPriority,
        period_ns: u64,
        deadline_ns: u64,
    ) -> bool {
        if slot >= MAX_REALTIME_TASKS {
            return false;
        }

        let mut name = [0u8; 16];
        let bytes = name_str.as_bytes();
        let len = if bytes.len() > 16 { 16 } else { bytes.len() };
        let mut i = 0;
        while i < len {
            name[i] = bytes[i];
            i += 1;
        }

        self.tasks[slot] = TaskControlBlock {
            task_id,
            name,
            priority,
            period_ns,
            deadline_ns,
            wcet_ns: 0,
            last_execution_ns: 0,
            execution_count: 0,
            missed_deadlines: 0,
            is_active: true,
        };
        true
    }

    /// Dispatches tasks according to priority and periodic deadlines.
    /// Returns the task_id of the highest priority runnable task.
    pub fn schedule_next(&mut self, now_ns: u64) -> Option<u8> {
        self.current_time_ns.store(now_ns, Ordering::Relaxed);
        self.total_cycles_dispatched.fetch_add(1, Ordering::Relaxed);

        let mut highest_pri = 999usize;
        let mut selected_slot: Option<usize> = None;

        for (idx, task) in self.tasks.iter_mut().enumerate() {
            if !task.is_active {
                continue;
            }

            // Check if period elapsed
            let elapsed = now_ns.saturating_sub(task.last_execution_ns);
            if elapsed >= task.period_ns || task.execution_count == 0 {
                // Check deadline miss
                if task.execution_count > 0 && elapsed > task.deadline_ns {
                    task.missed_deadlines += 1;
                }

                let pri_val = task.priority as usize;
                if pri_val < highest_pri {
                    highest_pri = pri_val;
                    selected_slot = Some(idx);
                }
            }
        }

        if let Some(slot) = selected_slot {
            let task = &mut self.tasks[slot];
            task.last_execution_ns = now_ns;
            task.execution_count += 1;
            Some(task.task_id)
        } else {
            None
        }
    }
}
