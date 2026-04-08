# Memory Hierarchy Simulation (SSD → DRAM → Cache → CPU)

## Overview

This project simulates a processor memory hierarchy where 32-bit instructions travel through multiple levels of storage: **SSD → DRAM → L3 → L2 → L1 → CPU**. The system enforces strict hierarchical data movement and models realistic behaviors such as latency, bandwidth, and cache replacement.

---

## Features

* Multi-level memory system:

  * SSD (largest storage)
  * DRAM
  * Cache hierarchy (L3, L2, L1)
* Strict hierarchy (no bypassing levels)
* Clock-driven simulation
* Configurable:

  * Memory sizes
  * Latency between levels
  * Bandwidth per transfer
* Read and write operations
* Cache eviction handling
* Replacement policies:

  * LRU (Least Recently Used)
  * FIFO (First In First Out)
  * Random
* Detailed output:

  * Instruction access trace
  * Data movement between levels
  * Cache hits and misses
  * Final state of memory

---

## How It Works

1. Instructions are initially stored in SSD.
2. When the CPU requests an instruction:

   * The system checks L1 → L2 → L3 → DRAM → SSD.
   * If not found, the instruction is fetched from lower levels.
3. Data moves upward through each level (no skipping).
4. Each transfer takes a defined number of clock cycles.
5. If a cache is full, an instruction is evicted based on the selected policy.

---

## Example Data Flow

SSD → DRAM → L3 → L2 → L1 → CPU

---

## How to Run

### Requirements

* Python 3

### Run the program

```bash
python3 task3.py
```

---

## Sample Output Includes

* Memory configuration
* Clock cycle simulation
* Instruction trace
* Cache hit/miss statistics
* Final memory state

---

## File Structure

```
Memory-Hierarchy-Simulation/
│── task3.py
│── README.md
```

---

## Author

Jeremie Saint Amour

---

## Notes

This project was developed as part of a computer architecture / systems assignment to model realistic memory hierarchy behavior in modern processors.
