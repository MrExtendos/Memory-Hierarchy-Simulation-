from collections import deque
import random


class Instruction:
    def __init__(self, value):
        if not (0 <= value <= 0xFFFFFFFF):
            raise ValueError(f"Instruction {value} is not a valid 32-bit value.")
        self.value = value

    def __repr__(self):
        return f"0x{self.value:08X}"


class MemoryLevel:
    def __init__(self, name, capacity, replacement_policy="FIFO"):
        self.name = name
        self.capacity = capacity
        self.replacement_policy = replacement_policy.upper()
        self.storage = deque()
        self.access_order = []

    def contains(self, instr):
        return any(x.value == instr.value for x in self.storage)

    def is_full(self):
        return len(self.storage) >= self.capacity

    def add(self, instr):
        if self.contains(instr):
            self.touch(instr)
            return None

        evicted = None
        if self.is_full():
            evicted = self.evict()

        self.storage.append(instr)
        self._record_access(instr)
        return evicted

    def remove(self, instr):
        for i, item in enumerate(self.storage):
            if item.value == instr.value:
                removed = self.storage[i]
                del self.storage[i]
                self._remove_access(instr)
                return removed
        return None

    def evict(self):
        if not self.storage:
            return None

        if self.replacement_policy == "FIFO":
            evicted = self.storage.popleft()
            self._remove_access(evicted)
            return evicted

        elif self.replacement_policy == "LRU":
            if not self.access_order:
                evicted = self.storage.popleft()
                return evicted
            lru_instr = self.access_order.pop(0)
            for i, item in enumerate(self.storage):
                if item.value == lru_instr.value:
                    evicted = self.storage[i]
                    del self.storage[i]
                    return evicted

        elif self.replacement_policy == "RANDOM":
            idx = random.randint(0, len(self.storage) - 1)
            evicted = self.storage[idx]
            del self.storage[idx]
            self._remove_access(evicted)
            return evicted

        else:
            raise ValueError(f"Unknown replacement policy: {self.replacement_policy}")

    def touch(self, instr):
        if self.replacement_policy == "LRU":
            self._remove_access(instr)
            self.access_order.append(instr)

    def _record_access(self, instr):
        if self.replacement_policy == "LRU":
            self._remove_access(instr)
            self.access_order.append(instr)
        elif self.replacement_policy == "FIFO":
            self.access_order.append(instr)

    def _remove_access(self, instr):
        self.access_order = [x for x in self.access_order if x.value != instr.value]

    def __repr__(self):
        return f"{self.name}: {[str(x) for x in self.storage]}"


class TransferRequest:
    def __init__(self, src, dst, instructions, latency, kind="READ"):
        self.src = src
        self.dst = dst
        self.instructions = instructions
        self.latency_remaining = latency
        self.kind = kind

    def tick(self):
        self.latency_remaining -= 1

    def ready(self):
        return self.latency_remaining <= 0

    def __repr__(self):
        return (
            f"{self.kind}: {self.src.name if self.src else 'CPU'} -> "
            f"{self.dst.name if self.dst else 'CPU'} | "
            f"{[str(i) for i in self.instructions]} | "
            f"{self.latency_remaining} cycles left"
        )


class MemoryHierarchy:
    def __init__(
        self,
        ssd_size,
        dram_size,
        l3_size,
        l2_size,
        l1_size,
        latencies,
        bandwidths,
        replacement_policy="FIFO",
    ):
        if not (ssd_size > dram_size > l3_size > l2_size > l1_size):
            raise ValueError("Hierarchy must satisfy SSD > DRAM > L3 > L2 > L1")

        self.ssd = MemoryLevel("SSD", ssd_size, replacement_policy)
        self.dram = MemoryLevel("DRAM", dram_size, replacement_policy)
        self.l3 = MemoryLevel("L3", l3_size, replacement_policy)
        self.l2 = MemoryLevel("L2", l2_size, replacement_policy)
        self.l1 = MemoryLevel("L1", l1_size, replacement_policy)

        self.levels = [self.ssd, self.dram, self.l3, self.l2, self.l1]

        self.latencies = latencies
        self.bandwidths = bandwidths
        self.cycle = 0
        self.pending_transfers = []

        self.trace = []
        self.hits = {"L1": 0, "L2": 0, "L3": 0}
        self.misses = {"L1": 0, "L2": 0, "L3": 0}

    def load_ssd(self, instruction_values):
        for value in instruction_values:
            self.ssd.add(Instruction(value))

    def find_level_containing(self, instr):
        for level in reversed(self.levels):
            if level.contains(instr):
                return level
        return None

    def schedule_transfer(self, src, dst, instructions, link_name, kind="READ"):
        bw = self.bandwidths[link_name]
        latency = self.latencies[link_name]

        chunk = instructions[:bw]
        req = TransferRequest(src, dst, chunk, latency, kind)
        self.pending_transfers.append(req)
        self.trace.append(
            f"[Cycle {self.cycle}] Scheduled {kind} transfer "
            f"{src.name if src else 'CPU'} -> {dst.name if dst else 'CPU'} : "
            f"{[str(i) for i in chunk]} (latency={latency})"
        )

        return instructions[bw:]

    def process_cycle(self):
        self.cycle += 1
        self.trace.append(f"\n=== Clock Cycle {self.cycle} ===")

        completed = []
        for req in self.pending_transfers:
            req.tick()
            self.trace.append(f"[Cycle {self.cycle}] In progress: {req}")
            if req.ready():
                completed.append(req)

        for req in completed:
            self.complete_transfer(req)
            self.pending_transfers.remove(req)

    def complete_transfer(self, req):
        for instr in req.instructions:
            if req.dst is not None:
                evicted = req.dst.add(instr)
                self.trace.append(
                    f"[Cycle {self.cycle}] Completed {req.kind}: "
                    f"{req.src.name if req.src else 'CPU'} -> {req.dst.name} : {instr}"
                )

                if evicted:
                    self.trace.append(
                        f"[Cycle {self.cycle}] Evicted from {req.dst.name}: {evicted}"
                    )
                    self.write_back(req.dst, evicted)
            else:
                self.trace.append(
                    f"[Cycle {self.cycle}] CPU received instruction: {instr}"
                )

    def write_back(self, current_level, instr):
        level_order = {
            "L1": self.l2,
            "L2": self.l3,
            "L3": self.dram,
            "DRAM": self.ssd,
            "SSD": None,
        }

        next_level = level_order.get(current_level.name)
        if next_level is None:
            return

        link_name = f"{current_level.name}->{next_level.name}"
        self.schedule_transfer(current_level, next_level, [instr], link_name, kind="WRITE")

    def read_instruction(self, value):
        instr = Instruction(value)
        self.trace.append(f"\n[Cycle {self.cycle}] READ request for instruction {instr}")

        if self.l1.contains(instr):
            self.hits["L1"] += 1
            self.l1.touch(instr)
            self.trace.append(f"[Cycle {self.cycle}] L1 HIT: {instr}")
            return

        self.misses["L1"] += 1
        self.trace.append(f"[Cycle {self.cycle}] L1 MISS: {instr}")

        if self.l2.contains(instr):
            self.hits["L2"] += 1
            self.l2.touch(instr)
            self.trace.append(f"[Cycle {self.cycle}] L2 HIT: {instr}")
            self.move_up(instr, start_level=self.l2)
            return

        self.misses["L2"] += 1
        self.trace.append(f"[Cycle {self.cycle}] L2 MISS: {instr}")

        if self.l3.contains(instr):
            self.hits["L3"] += 1
            self.l3.touch(instr)
            self.trace.append(f"[Cycle {self.cycle}] L3 HIT: {instr}")
            self.move_up(instr, start_level=self.l3)
            return

        self.misses["L3"] += 1
        self.trace.append(f"[Cycle {self.cycle}] L3 MISS: {instr}")

        source = self.find_level_containing(instr)
        if source is None:
            self.trace.append(f"[Cycle {self.cycle}] Instruction {instr} not found anywhere.")
            return

        self.move_up(instr, start_level=source)

    def move_up(self, instr, start_level):
        order = [self.ssd, self.dram, self.l3, self.l2, self.l1]
        idx = order.index(start_level)

        for i in range(idx, len(order) - 1):
            src = order[i]
            dst = order[i + 1]
            link_name = f"{src.name}->{dst.name}"
            self.schedule_transfer(src, dst, [instr], link_name, kind="READ")

        self.schedule_transfer(self.l1, None, [instr], "L1->CPU", kind="READ")

    def write_instruction(self, value):
        instr = Instruction(value)
        self.trace.append(f"\n[Cycle {self.cycle}] WRITE request for instruction {instr}")

        if self.l1.contains(instr):
            self.trace.append(f"[Cycle {self.cycle}] Updating instruction already in L1: {instr}")
            self.l1.touch(instr)
        else:
            evicted = self.l1.add(instr)
            self.trace.append(f"[Cycle {self.cycle}] Written to L1: {instr}")
            if evicted:
                self.trace.append(f"[Cycle {self.cycle}] Evicted from L1 due to write: {evicted}")
                self.write_back(self.l1, evicted)

    def print_configuration(self):
        print("=== Memory Hierarchy Configuration ===")
        print(f"SSD size  : {self.ssd.capacity} instructions")
        print(f"DRAM size : {self.dram.capacity} instructions")
        print(f"L3 size   : {self.l3.capacity} instructions")
        print(f"L2 size   : {self.l2.capacity} instructions")
        print(f"L1 size   : {self.l1.capacity} instructions")
        print(f"Replacement Policy: {self.l1.replacement_policy}")
        print("\nLatencies:")
        for k, v in self.latencies.items():
            print(f"  {k}: {v} cycles")
        print("\nBandwidths:")
        for k, v in self.bandwidths.items():
            print(f"  {k}: {v} instruction(s)/cycle")
        print()

    def print_trace(self):
        print("=== Instruction Access Trace ===")
        for line in self.trace:
            print(line)
        print()

    def print_stats(self):
        print("=== Cache Hits / Misses ===")
        for level in ["L1", "L2", "L3"]:
            print(f"{level} Hits   : {self.hits[level]}")
            print(f"{level} Misses : {self.misses[level]}")
        print()

    def print_final_state(self):
        print("=== Final State of Each Memory Level ===")
        for level in self.levels:
            print(level)
        print()


def main():
    latencies = {
        "SSD->DRAM": 5,
        "DRAM->L3": 4,
        "L3->L2": 3,
        "L2->L1": 2,
        "L1->CPU": 1,
        "L1->L2": 2,
        "L2->L3": 3,
        "L3->DRAM": 4,
        "DRAM->SSD": 5,
    }

    bandwidths = {
        "SSD->DRAM": 2,
        "DRAM->L3": 2,
        "L3->L2": 2,
        "L2->L1": 1,
        "L1->CPU": 1,
        "L1->L2": 1,
        "L2->L3": 1,
        "L3->DRAM": 1,
        "DRAM->SSD": 1,
    }

    mem = MemoryHierarchy(
        ssd_size=20,
        dram_size=12,
        l3_size=8,
        l2_size=4,
        l1_size=2,
        latencies=latencies,
        bandwidths=bandwidths,
        replacement_policy="LRU",   # FIFO, LRU, or RANDOM
    )

    mem.load_ssd([
        0x10000001, 0x10000002, 0x10000003, 0x10000004,
        0x10000005, 0x10000006, 0x10000007, 0x10000008
    ])

    mem.print_configuration()

    mem.read_instruction(0x10000001)
    for _ in range(16):
        mem.process_cycle()

    mem.read_instruction(0x10000001)
    for _ in range(3):
        mem.process_cycle()

    mem.read_instruction(0x10000002)
    for _ in range(16):
        mem.process_cycle()

    mem.read_instruction(0x10000003)
    for _ in range(16):
        mem.process_cycle()

    mem.write_instruction(0xABCDEF01)
    for _ in range(8):
        mem.process_cycle()

    mem.print_trace()
    mem.print_stats()
    mem.print_final_state()


if __name__ == "__main__":
    main()