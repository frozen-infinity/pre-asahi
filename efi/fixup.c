/* QEMU-only APPLY test: private pool buffers, no reserve/install or OS launch. */
#define efi_main discovery_main
#include "probe.c"
#undef efi_main
#include "synthetic-fdt.h"
_Static_assert(__builtin_offsetof(BOOT, allocate) == 64, "EFI AllocatePool offset");
_Static_assert(__builtin_offsetof(BOOT, release) == 72, "EFI FreePool offset");
typedef STATUS (*APPLY)(FIXUP *, void *, UINTN *, U32);
static U32 be32(const U8 *p) { return (U32)p[0]<<24 | (U32)p[1]<<16 | (U32)p[2]<<8 | p[3]; }
static void reset(U8 *p) { for (UINTN i=0; i<sizeof(fixture); i++) p[i]=fixture[i]; }
STATUS efi_main(void *image, SYSTEM *system)
{
    STATUS result = discovery_main(image, system);
    if (result) return result;
    if (!system->boot->allocate || !system->boot->release) return ERROR(2);
    GUID guid = {0xe617d64c,0xfe08,0x46da,{0xf4,0xdc,0xbb,0xd5,0x87,0x0c,0x73,0x00}};
    FIXUP *protocol = 0;
    result = system->boot->locate(&guid, 0, (void **)&protocol);
    if (result || !protocol || !protocol->fixup || protocol->revision != 0x10000) return ERROR(2);
    APPLY apply = (APPLY)protocol->fixup;
    U8 *small = 0, *large = 0;
    UINTN size = sizeof(fixture);
    result = system->boot->allocate(2, size, (void **)&small);
    if (result || !small) return result ? result : ERROR(9);
    result = ERROR(2);
    reset(small);
    if (apply(protocol, small, &size, 1) != ERROR(5) || size <= sizeof(fixture) || size > 2*1024*1024)
        goto done;
    for (UINTN i=0; i<sizeof(fixture); i++) if (small[i]!=fixture[i]) goto done;
    say(system, "PRE_ASAHI_BUFFER_NEGOTIATED");
    if (system->boot->allocate(2, size, (void **)&large) || !large) goto done;
    reset(large);
    UINTN capacity = size;
    if (apply(protocol, large, &size, 0) != ERROR(2)) goto done;
    if (apply(protocol, large, &size, 8) != ERROR(2)) goto done;
    large[0] = 0;
    if (apply(protocol, large, &size, 1) != ERROR(2)) goto done;
    say(system, "PRE_ASAHI_INVALID_INPUT_REJECTED");
    reset(large);
    size = capacity;
    /* APPLY only. Never request memory reservation or configuration table installation. */
    if (apply(protocol, large, &size, 1) || be32(large)!=0xd00dfeed ||
        be32(large+4) > capacity || be32(large+4) < sizeof(fixture)) goto done;
    result = 0;
done:
    if (large && system->boot->release(large)) result = ERROR(2);
    if (system->boot->release(small)) result = ERROR(2);
    say(system, result ? "PRE_ASAHI_FIXUP_FAILED" : "PRE_ASAHI_FIXUP_APPLY_PASS");
    say(system, "PRE_ASAHI_NO_LINUX_LAUNCH");
    return result;
}
