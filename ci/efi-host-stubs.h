/* Host-only substitutes for EFI services and hardware helper; never firmware. */
#ifndef PRE_ASAHI_EFI_HOST_STUBS_H
#define PRE_ASAHI_EFI_HOST_STUBS_H
#define EFIAPI
#define __maybe_unused __attribute__((unused))
#define EFI_ENTRY(...) ((void)0)
#define EFI_EXIT(status) (status)
#define log_err(...) ((void)0)
#define log_debug(...) ((void)0)
#define EFI_SUCCESS 0ULL
#define EFI_INVALID_PARAMETER ((1ULL << 63) | 2)
#define EFI_BUFFER_TOO_SMALL ((1ULL << 63) | 5)
#define EFI_NOT_FOUND ((1ULL << 63) | 14)
#define EFI_RESERVED_MEMORY_TYPE 0
#define EFI_BOOT_SERVICES_DATA 4
#define EFI_DT_FIXUP_PROTOCOL_GUID {{0, 0, 0, 0}}
#define EFI_RNG_PROTOCOL_GUID {{1, 0, 0, 0}}
#define EFI_DT_APPLY_FIXUPS 1
#define EFI_DT_RESERVE_MEMORY 2
#define EFI_DT_INSTALL_TABLE 4
#define EFI_DT_ALL 7
#define EFI_DT_FIXUP_PROTOCOL_REVISION 0x10000
#define CONFIG_SYS_FDT_PAD 0x40000
#define CONFIG_APPLE_J713_FDT 1
#define CONFIG_APPLE_MTP_KEYB 1
#define IS_ENABLED(value) (value)
#define UCLASS_KEYBOARD 1
#define FDT_ADDR_T_NONE UINT64_MAX
typedef u64 efi_status_t;
typedef size_t efi_uintn_t;
typedef u64 fdt_addr_t;
typedef u64 fdt_size_t;
typedef struct { unsigned int word[4]; } efi_guid_t;
struct bootm_headers { int unused; };
struct bd_info { int unused; };
struct udevice { int unused; };
struct efi_handler { int unused; };
struct efi_dt_fixup_protocol {
    u64 revision;
    efi_status_t (*fixup)(struct efi_dt_fixup_protocol *, void *, efi_uintn_t *, u32);
};
extern struct efi_dt_fixup_protocol efi_dt_fixup_prot;
static const efi_guid_t efi_guid_fdt = {{2, 0, 0, 0}};
static void *efi_root;
static struct { const void *fdt_blob; } host_gd;
#define gd (&host_gd)
static int helper_result, helper_calls, setup_calls, reserved_calls, install_calls;
static void *published_tree;
static efi_status_t efi_add_memory_map(u64 address, u64 size, int type)
{ (void)address; (void)size; (void)type; reserved_calls++; return EFI_SUCCESS; }
static void *map_sysmem(u64 address, unsigned long size)
{ (void)size; return (void *)(uintptr_t)address; }
static efi_status_t efi_search_protocol(void *root, const efi_guid_t *guid, struct efi_handler **handler)
{ (void)root; (void)guid; (void)handler; return EFI_NOT_FOUND; }
static efi_status_t efi_install_configuration_table(const efi_guid_t *guid, void *tree)
{ (void)guid; install_calls++; published_tree = tree; return EFI_SUCCESS; }
static bool fdtdec_get_is_enabled(const void *tree, int node)
{
    const char *status = fdt_getprop(tree, node, "status", NULL);
    return !status || !strcmp(status, "okay") || !strcmp(status, "ok");
}
static bool fdtdec_get_bool(const void *tree, int node, const char *name)
{ return fdt_getprop(tree, node, name, NULL) != NULL; }
static fdt_addr_t fdtdec_get_addr_size_auto_parent(const void *tree, int parent, int node,
                                                const char *name, int index, fdt_size_t *size, bool translate)
{
    (void)parent; (void)index; (void)translate;
    int length;
    const fdt64_t *reg = fdt_getprop(tree, node, name, &length);
    if (!reg || length < 16) return FDT_ADDR_T_NONE;
    *size = fdt64_to_cpu(reg[1]);
    return fdt64_to_cpu(reg[0]);
}
static bool of_machine_is_compatible(const char *compatible)
{ return !fdt_node_check_compatible(gd->fdt_blob, 0, compatible); }
static int apple_rtkit_helper_fdt_fixup(void *tree)
{ (void)tree; helper_calls++; return helper_result; }
static unsigned int current_el(void) { return 2; }
static int uclass_find_device(int class, int index, struct udevice **device)
{ (void)class; (void)index; (void)device; return -ENODEV; }
static const char *env_get(const char *name) { (void)name; return NULL; }
static int ft_board_setup(void *blob, struct bd_info *bd);
static int image_setup_libfdt(struct bootm_headers *image, void *tree, bool log)
{ (void)image; (void)log; setup_calls++; return ft_board_setup(tree, NULL); }
#endif
