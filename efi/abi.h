#ifndef PRE_ASAHI_EFI_ABI_H
#define PRE_ASAHI_EFI_ABI_H
typedef __UINT8_TYPE__ U8;
typedef __UINT16_TYPE__ U16;
typedef __UINT32_TYPE__ U32;
typedef __UINT64_TYPE__ U64;
typedef __UINTPTR_TYPE__ UINTN;
typedef U64 STATUS;
typedef struct { U32 a; U16 b, c; U8 d[8]; } GUID;
typedef struct { U64 signature; U32 revision, size, crc, reserved; } HEADER;
typedef struct TEXT TEXT;
struct TEXT { void *reset; STATUS (*output)(TEXT *, U16 *); };
typedef struct { HEADER header; void *unused_before_pool[5]; STATUS (*allocate)(U32, UINTN, void **); STATUS (*release)(void *); void *unused_before_install[14]; STATUS (*install_table)(GUID *, void *); void *unused_after_install[15]; STATUS (*locate)(GUID *, void *, void **); } BOOT;
typedef struct {
    HEADER header;
    U16 *vendor;
    U32 firmware_revision;
    void *input_handle, *input, *output_handle;
    TEXT *output;
    void *error_handle, *error, *runtime;
    BOOT *boot;
    UINTN table_count;
    void *tables;
} SYSTEM;
typedef struct { GUID guid; void *table; } CONFIG_TABLE;

typedef struct { U64 revision; void *fixup; } FIXUP;
#define ERROR(code) ((1ULL << 63) | (code))
_Static_assert(sizeof(void *) == 8 && sizeof(GUID) == 16, "64-bit EFI layout required");
_Static_assert(__builtin_offsetof(SYSTEM, output) == 64, "EFI console offset");
_Static_assert(__builtin_offsetof(SYSTEM, boot) == 96 && sizeof(SYSTEM) == 120, "EFI system layout");
_Static_assert(__builtin_offsetof(BOOT, locate) == 320, "EFI LocateProtocol offset");

_Static_assert(__builtin_offsetof(BOOT, install_table) == 192, "EFI InstallConfigurationTable offset");

#endif
