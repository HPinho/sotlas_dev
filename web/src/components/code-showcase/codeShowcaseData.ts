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
    subtitle: "Hardware-oriented syntax shown as a design example; no device access is performed here.",
    levelBadge: "Illustrative syntax",
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
    // Illustrative syntax; this sample does not mask or restore interrupts.
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
        // A target backend must implement any required state restoration.
        rebound;
    }
}`,
    metrics: [
      { label: "Execution", value: "Not run", badge: "Example" },
      { label: "Hardware access", value: "Not validated", badge: "Preview" },
      { label: "Backend support", value: "Target dependent", badge: "Check docs" },
      { label: "Status", value: "Illustrative", badge: "Design" },
    ],
    logs: [
      { timeMs: 40, type: "hw", message: "Example source declares a *rawphys pointer." },
      { timeMs: 120, type: "cycle", message: "This panel does not invoke the compiler or mask interrupts." },
      { timeMs: 210, type: "srg", message: "DMA allocation and cache synchronization are not demonstrated." },
      { timeMs: 330, type: "hw", message: "Instruction selection depends on backend and target." },
      { timeMs: 450, type: "hw", message: "No processor instruction or timing is measured here." },
      { timeMs: 560, type: "cycle", message: "Persistence barriers require target-specific implementation." },
      { timeMs: 690, type: "ok", message: "See the release scope for supported source forms." },
      { timeMs: 820, type: "sys", message: "Illustrative output only; no hardware was accessed." },
    ],
  },
  {
    id: "native-srg",
    title: "High-Level & SRG Memory",
    subtitle: "Ownership and contract syntax with the limits of this illustrative example.",
    levelBadge: "Illustrative syntax",
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
        // This syntax does not establish general data-race freedom.
        quarantine buffer;
        
        // Dispatches to asynchronous queue consuming the 'island' region
        await self.dispatch(buffer);
        
        // Transfers ownership without triggering the destructor prematurely
        handover buffer;
    }

    pub fn process(event_id: UInt64) -> Bool => event_id != 0;
    pub async fn dispatch(data: island [UInt8; 512]) -> Void { /* illustrative */ }
}`,
    metrics: [
      { label: "Execution", value: "Not run", badge: "Example" },
      { label: "Ownership", value: "Subset only", badge: "SRG" },
      { label: "Concurrency", value: "Not proven here", badge: "Limits apply" },
      { label: "Type checks", value: "Backend dependent", badge: "Check docs" },
    ],
    logs: [
      { timeMs: 50, type: "sys", message: "Example source is displayed for discussion." },
      { timeMs: 140, type: "srg", message: "Ownership acceptance depends on the source form and compiler gate." },
      { timeMs: 250, type: "cycle", message: "This example does not prove general race freedom." },
      { timeMs: 380, type: "sys", message: "No async runtime is started by this page." },
      { timeMs: 510, type: "srg", message: "Transfer behavior is covered only for documented domain transitions." },
      { timeMs: 650, type: "ok", message: "Contracts are checked only for implemented forms." },
      { timeMs: 780, type: "sys", message: "Consult the release scope for tested cleanup paths." },
    ],
  },
  {
    id: "bit-slicing",
    title: "Bits, Endianness & Bounded",
    subtitle: "An illustrative parsing example; compiler acceptance and code generation are not evaluated here.",
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
      { label: "Execution", value: "Not run", badge: "Example" },
      { label: "Instruction cost", value: "Not measured", badge: "Backend" },
      { label: "Range checks", value: "Subset dependent", badge: "See gates" },
      { label: "Status", value: "Illustrative", badge: "Design" },
    ],
    logs: [
      { timeMs: 60, type: "hw", message: "No memory is read by this illustrative panel." },
      { timeMs: 160, type: "cycle", message: "The example shows a bit-slice expression." },
      { timeMs: 270, type: "cycle", message: "Range acceptance depends on the active compiler gate." },
      { timeMs: 400, type: "hw", message: "No device or mapped address is accessed." },
      { timeMs: 530, type: "cycle", message: "Endian lowering depends on backend and target." },
      { timeMs: 670, type: "ok", message: "Use the repository examples to validate compiler behavior." },
      { timeMs: 800, type: "sys", message: "No runtime or performance measurement is performed." },
    ],
  },
];
