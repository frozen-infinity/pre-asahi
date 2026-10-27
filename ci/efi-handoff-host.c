/* Run production EFI Fixup() and board hook with synthetic DTs/mocked services. */
#define main unused_os_tree_main
#include "j713-os-tree.c"
#undef main
#include "efi-host-stubs.h"
#include EFI_FIXUP_SOURCE
#include BOARD_HOOK_SOURCE

static void reset_services(void)
{
    setup_calls = helper_calls = reserved_calls = install_calls = 0;
    helper_result = 0;
    published_tree = NULL;
}

int main(int argc, char **argv)
{
    assert(argc == 3);
    void *tree = load_tree(argv[1], 1024 * 1024);
    void *runtime = load_tree(argv[2], J713_FDT_MAX_SOURCE);
    int cpus = match_synthetic_cpus(runtime, tree);
    gd->fdt_blob = runtime;
    size_t used = fdt_off_dt_strings(tree) + fdt_size_dt_strings(tree);
    size_t capacity = (used + CONFIG_SYS_FDT_PAD + 4095) & ~(size_t)4095;
    fdt_set_totalsize(tree, capacity);
    void *original = malloc(capacity);
    assert(original);
    memcpy(original, tree, capacity);
    efi_uintn_t size = capacity;
    reset_services();
    assert(efi_dt_fixup(NULL, tree, &size, EFI_DT_ALL) == EFI_INVALID_PARAMETER);
    assert(efi_dt_fixup(&efi_dt_fixup_prot, tree, &size, 0) == EFI_INVALID_PARAMETER);
    assert(!setup_calls && !install_calls && !memcmp(tree, original, capacity));
    size = 64;
    assert(efi_dt_fixup(&efi_dt_fixup_prot, tree, &size, EFI_DT_ALL) == EFI_BUFFER_TOO_SMALL);
    assert(size >= used + CONFIG_SYS_FDT_PAD && size <= capacity);
    assert(!setup_calls && !helper_calls && !reserved_calls && !install_calls);
    assert(!memcmp(tree, original, capacity));
    size = capacity;
    int chosen = fdt_path_offset(tree, "/chosen");
    assert(!fdt_setprop_string(tree, chosen, J713_FDT_SOURCE, "bad-identity"));
    assert(efi_dt_fixup(&efi_dt_fixup_prot, tree, &size, EFI_DT_ALL) == EFI_INVALID_PARAMETER);
    assert(!helper_calls && !install_calls && !reserved_calls);
    memcpy(tree, original, capacity);
    reset_services();
    helper_result = -EPERM;
    assert(efi_dt_fixup(&efi_dt_fixup_prot, tree, &size, EFI_DT_ALL) == EFI_INVALID_PARAMETER);
    assert(setup_calls == 1 && helper_calls == 1 && !install_calls && !reserved_calls);
    assert(!fdt_getprop(tree, fdt_path_offset(tree, "/chosen"), J713_FDT_COMPLETE, NULL));
    /* The import can change this working buffer before helper refusal. Rebuild it. */
    memcpy(tree, original, capacity);
    reset_services();
    assert(efi_dt_fixup(&efi_dt_fixup_prot, tree, &size, EFI_DT_ALL) == EFI_SUCCESS);
    assert(setup_calls == 1 && helper_calls == 1 && reserved_calls > 0 && install_calls == 1);
    assert(published_tree == tree);
    int length;
    const fdt32_t *complete = fdt_getprop(tree, fdt_path_offset(tree, "/chosen"), J713_FDT_COMPLETE, &length);
    assert(complete && length == 4 && fdt32_to_cpu(*complete) == 1);
    check_static_policy(original, tree);
    check_memory_references(tree);
    memcpy(tree, original, capacity);
    reset_services();
    assert(efi_dt_fixup(&efi_dt_fixup_prot, tree, &size, EFI_DT_APPLY_FIXUPS) == EFI_SUCCESS);
    assert(helper_calls == 1 && !reserved_calls && !install_calls && !published_tree);
    puts("{\"status\":\"HOST_EFI_SEQUENCE_PASS\",\"synthetic_cpu_count\":10,"
         "\"buffer_negotiation_passed\":true,\"bad_identity_not_published\":true,"
         "\"helper_refusal_not_published\":true,\"success_published_after_helper\":true,"
         "\"apply_only_does_not_publish\":true,\"efi_services_mocked\":true,\"helper_mocked\":true}");
    assert(cpus == 10);
    return 0;
}
