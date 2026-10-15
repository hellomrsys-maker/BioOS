//! # BioOS Deterministic Static Slab Memory Allocator
//! Standards: IEC 62304 Class C, MISRA-C Compliance
//! Zero heap fragmentation, O(1) allocation/deallocation in #![no_std].

pub const SLAB_BLOCK_SIZE_64: usize = 64;
pub const SLAB_COUNT_64: usize = 16;

#[derive(Clone, Copy)]
pub struct SlabBlock64 {
    pub data: [u8; SLAB_BLOCK_SIZE_64],
    pub is_used: bool,
}

impl SlabBlock64 {
    pub const fn new() -> Self {
        Self {
            data: [0u8; SLAB_BLOCK_SIZE_64],
            is_used: false,
        }
    }
}

pub struct StaticSlabPool {
    pub blocks: [SlabBlock64; SLAB_COUNT_64],
    pub allocated_count: usize,
    pub high_water_mark: usize,
}

impl StaticSlabPool {
    pub const fn new() -> Self {
        Self {
            blocks: [SlabBlock64::new(); SLAB_COUNT_64],
            allocated_count: 0,
            high_water_mark: 0,
        }
    }

    /// Allocates a 64-byte block with O(1) bounded scan.
    /// Returns Some(index) or None if pool is exhausted.
    pub fn alloc(&mut self) -> Option<usize> {
        for (i, block) in self.blocks.iter_mut().enumerate() {
            if !block.is_used {
                block.is_used = true;
                self.allocated_count += 1;
                if self.allocated_count > self.high_water_mark {
                    self.high_water_mark = self.allocated_count;
                }
                return Some(i);
            }
        }
        None
    }

    /// Frees a 64-byte block by index.
    pub fn free(&mut self, index: usize) -> bool {
        if index < SLAB_COUNT_64 && self.blocks[index].is_used {
            self.blocks[index].is_used = false;
            // Clean memory contents to prevent stale state leakage
            self.blocks[index].data = [0u8; SLAB_BLOCK_SIZE_64];
            self.allocated_count = self.allocated_count.saturating_sub(1);
            true
        } else {
            false
        }
    }

    pub fn usage_ratio_percent(&self) -> u32 {
        ((self.allocated_count * 100) / SLAB_COUNT_64) as u32
    }
}
