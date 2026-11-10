# Virtual memory in the native x86-64 kernel

The `barecore` kernel can install its own page-table root and manage 4 KiB
supervisor mappings in the virtual range `[0x40000000, 0x80000000)`. It
retains the bootstrap identity map below 1 GiB for the image, stack,
interrupt tables and allocator. The compiler emits the privileged
instructions directly and rejects their objects at hosted link boundaries.

## Build and boot

```sh
bash scripts/build_kernel.sh build/native/sotlas-native build/kernel-vm --vm --run
```

Use a rebuilt compiler with paging support, a fresh output directory and
QEMU x86-64. The example uses the Sotlas physical page allocator and the
existing IDT. It runs with host tools absent from the compiler's PATH.

## Mapping contract

- Initialize the physical allocator and install the IDT first. Call
  `native_kernel_vm_init()` once. It retains three physical pages for the
  new root, PDPT and directory. A CPU without NX support leaves the previous
  root active and the tentative allocation is released.
- `native_kernel_vm_map(virtual, physical, access)` installs a single page.
  Both addresses must be aligned. It refuses an occupied slot, an unsupported
  access mode or an unavailable table allocation. The first mapping in each
  2 MiB band allocates a zeroed page table.
- RAM modes are read-only, read/write and read/execute. The processor enforces
  supervisor write protection through CR0.WP and execution protection through
  EFER.NXE. `native_kernel_vm_protect` changes a RAM mapping in place.
- MMIO mode maps a caller-verified device page from 1 GiB to below 4 GiB
  with PCD and PWT set and execution disabled. The mode assumes the
  bootstrap PAT layout. It rejects addresses already covered by the low
  identity map and cannot be changed to a RAM mode with `protect`.
- `native_kernel_vm_physical` resolves a byte address within a live
  mapping. `native_kernel_vm_unmap` removes an aligned mapping, invalidates
  the local translation and returns the borrowed physical page address.
  The runtime releases a page table when its last mapping is removed.
- Callers keep RAM frames allocated for the lifetime of all mappings and
  stop using aliases before releasing them. The integer physical address
  carries no provenance. Callers also own device discovery, cache alias
  checks, and the ordering and width of device accesses.

The runtime serializes table edits by saving and restoring IF on the bootstrap
processor. One root remains installed for the lifetime of the kernel.
Permissions apply to the managed virtual aliases. The bootstrap identity
map remains writable and executable, so this profile does not enforce
system-wide W^X. Separate user address spaces, user privilege transitions,
SMP and remote TLB shootdowns are outside this profile.
See the [Intel system programming manual](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html)
for paging-mode modifiers, invalidation and page-fault error codes.

## Verification

The guest checks a supervisor write fault on a read-only page, an instruction
fetch fault on an NX page, a successful fetch after changing the mapping to
RX, and a not-present fault after unmapping a previously accessed page. Its
handler checks CR2 and the error code. The example remaps the missing page
and resumes the faulting read. It checks table sharing and reclamation across
two directory entries, the bounds and protection of MMIO mappings, and
preservation of existing mappings when the physical allocator runs out of pages.

The Linux QEMU gate boots with 32, 64 and 128 MiB RAM. It also boots with NX
hidden and checks that initialization fails without consuming physical pages.
The Windows and Intel macOS gates build and inspect the image and exercise
link-time rejection.
