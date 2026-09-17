export interface ExecutionLog {
  timeMs: number;
  type: "srg" | "hw" | "sys" | "ok" | "cycle";
  message: string;
  highlight?: string;
}

export interface MetricData {
  label: string;
  value: string;
  badge?: string;
}

export interface CodeScenario {
  id: string;
  title: string;
  subtitle: string;
  levelBadge: string;
  profile: string;
  filename: string;
  code: string;
  logs: ExecutionLog[];
  metrics: MetricData[];
}

export const codeScenarios: CodeScenario[] = [
  {
    id: "barecore",
    title: "Low-Level & Hardware",
    subtitle: "MMIO control, atomic critical sections, and hardware bus-aligned registers.",
    levelBadge: "Bare-Metal / Kernel",
    profile: "target barecore;",
    filename: "drivers/dma_controller.sot",
    code: `target barecore;
module kernel::drivers::dma;

// Physical memory layout mapped with hardware bus alignment
mesh DmaChannelRegisters {
    source_addr:   *rawphys UInt64 align(8);
    dest_addr:     *rawphys UInt64 align(8);
    transfer_len:  UInt32          align(4);
    control_flags: UInt32          align(4);
}

pub fn transfer_packet(channel: *rawphys mut DmaChannelRegisters, data: *dmazone UInt8, len: UInt32) -> Void {
    // Critical section with guaranteed atomic restoration of interrupt flags
    clinch {
        // Native bit-slicing for channel extraction and flags
        let burst_mode = channel.control_flags.slit[0..3];
        channel.source_addr = data as *rawphys UInt64;
        channel.transfer_len = len;
        
        // Atomic transfer trigger with interrupt flag
        channel.control_flags = (burst_mode | 0x80).strand;
        
        // Physical memory persistence barrier
        quench {
            gate(channel.transfer_len > 0) { return; }
        }
    } revert {
        // Guarantee CPU flags restoration if aborted or interrupted
        rebound;
    }
}`,
    metrics: [
      { label: "Runtime Overhead", value: "0.00 ns", badge: "Zero-Cost" },
      { label: "Memory Model", value: "MMIO Direct", badge: "*rawphys" },
      { label: "Section Guarantee", value: "Atomic CLI/STI", badge: "clinch" },
      { label: "Allocator / GC", value: "0 B (No Runtime)", badge: "Freestanding" },
    ],
    logs: [
      { timeMs: 40, type: "hw", message: "Initializing MMIO mapping at address 0xFD002000 (*rawphys)" },
      { timeMs: 120, type: "cycle", message: "[clinch] Critical section entered. Interrupt flags atomically masked." },
      { timeMs: 210, type: "srg", message: "DMA Zone aligned: 4096 bytes mapped via *dmazone zero-copy." },
      { timeMs: 330, type: "hw", message: ".slit[0..3] operation: burst mode field extracted (0x02) in 1 cycle." },
      { timeMs: 450, type: "hw", message: ".strand operation: endianness swapped instantly via bswap instruction." },
      { timeMs: 560, type: "cycle", message: "[quench] Memory persistence barrier synchronized successfully." },
      { timeMs: 690, type: "ok", message: "[revert] Block finalized with state integrity guaranteed." },
      { timeMs: 820, type: "sys", message: "DMA transfer completed in 0.14 µs. 0 dynamic allocations." },
    ],
  },
  {
    id: "native-srg",
    title: "High-Level & SRG Memory",
    subtitle: "Spec contracts, deterministic management without GC, and Island concurrency.",
    levelBadge: "Systems & Apps",
    profile: "target native;",
    filename: "services/event_dispatcher.sot",
    code: `target native;
module services::dispatcher;

// Compile-time verified API contract without .h headers
pub spec EventProcessor {
    fn process(event_id: UInt64) -> Bool;
    async fn dispatch(data: island [UInt8; 512]) -> Void;
}

pub class MessageServer adopts EventProcessor {
    pub let port: UInt16.bound[1024..65535];
    
    pub init(p: UInt16.bound[1024..65535]) {
        self.port = p;
    }

    pub async fn route_packet(buffer: sole [UInt8; 512]) -> Void {
        // Isolates data for concurrent execution guaranteeing zero data races
        quarantine buffer;
        
        // Dispatches to asynchronous queue consuming the 'island' region
        await self.dispatch(buffer);
        
        // Transfers ownership without triggering the destructor prematurely
        handover buffer;
    }

    pub fn process(event_id: UInt64) -> Bool => event_id != 0;
    pub async fn dispatch(data: island [UInt8; 512]) -> Void { /* Async I/O */ }
}`,
    metrics: [
      { label: "Memory Manager", value: "AST Scope Graph", badge: "SRG" },
      { label: "Data Race Safety", value: "Statically Proven", badge: "island" },
      { label: "GC Pauses", value: "0.0 ms (Deterministic)", badge: "No GC" },
      { label: "Bounded Type", value: "1024..65535", badge: "Verified" },
    ],
    logs: [
      { timeMs: 50, type: "sys", message: "Starting MessageServer on port 8080 (BoundedType verified)." },
      { timeMs: 140, type: "srg", message: "[sole] Exclusive buffer [512 B] allocation registered in lexical scope." },
      { timeMs: 250, type: "cycle", message: "[quarantine] Buffer successfully isolated in 'island' region. Data races impossible." },
      { timeMs: 380, type: "sys", message: "[async/await] Non-blocking dispatch on native runtime worker." },
      { timeMs: 510, type: "srg", message: "[handover] Static ownership transferred to receiver; zero copies in memory." },
      { timeMs: 650, type: "ok", message: "Spec 'EventProcessor' satisfied with 100% contract compliance." },
      { timeMs: 780, type: "sys", message: "Scope cycle closed: memory reclaimed deterministically via AST." },
    ],
  },
  {
    id: "bit-slicing",
    title: "Bits, Endianness & Bounded",
    subtitle: "Binary packet slicing without manual bit-shifts and compile-time bounds checking.",
    levelBadge: "Protocols & Network",
    profile: "target native;",
    filename: "network/ipv4_parser.sot",
    code: `target native;
module network::protocol::ipv4;

pub struct IpHeader {
    pub version:     UInt8.bound[4..6];
    pub ihl:         UInt8.bound[5..15];
    pub total_len:   UInt16;
    pub flags:       UInt8;
}

pub fn decode_header(raw: *virtmap UInt32) -> IpHeader? {
    let dword0: UInt32 = *raw;
    
    // Extracts version (bits 28..31) and IHL (bits 24..27) directly
    let version_val = dword0.slit[28..31] as UInt8;
    let ihl_val     = dword0.slit[24..27] as UInt8;
    
    // Inspects isolated 'Don't Fragment' flag bit
    let flag_df = dword0.notch[14] == 1;
    
    guard version_val == 4 else {
        return nil;
    }

    return IpHeader {
        version: version_val as UInt8.bound[4..6],
        ihl: ihl_val as UInt8.bound[5..15],
        total_len: (dword0.slit[0..15] as UInt16).strand,
        flags: flag_df ? 0x02 : 0x00,
    };
}`,
    metrics: [
      { label: "Bit-Slice Cost", value: "0 Extra Cycles", badge: ".slit" },
      { label: "Endian Conversion", value: "1 Opcode (bswap)", badge: ".strand" },
      { label: "Type Safety", value: "UInt8.bound", badge: "Compile-time" },
      { label: "Null Safety", value: "Type? with nil", badge: "No NULL" },
    ],
    logs: [
      { timeMs: 60, type: "hw", message: "Reading raw DWORD from *virtmap virtual address space (0x7FFF8000)." },
      { timeMs: 160, type: "cycle", message: "Executing .slit[28..31]: IPv4 Version = 4 extracted directly." },
      { timeMs: 270, type: "cycle", message: "Executing .slit[24..27]: IHL = 5 (20 header bytes) validated." },
      { timeMs: 400, type: "hw", message: "Executing .notch[14]: DF (Don't Fragment) flag detected active." },
      { timeMs: 530, type: "cycle", message: "Executing .strand: Total length converted to target host endianness." },
      { timeMs: 670, type: "ok", message: "IpHeader struct instantiated with valid BoundedTypes." },
      { timeMs: 800, type: "sys", message: "Decoding finished in 12 CPU instructions (6.2 ns latency)." },
    ],
  },
];
