/* Workspace-only OS DT preparation/probing. Uses the pinned production importer. */
#define J713_FDT_HOST_TEST
#include J713_IMPORTER_SOURCE
#include <assert.h>
#include <stdio.h>

static void *load_tree(const char *path, size_t capacity)
{
    FILE *file = fopen(path, "rb");
    assert(file && !fseek(file, 0, SEEK_END));
    long length = ftell(file);
    assert(length >= 40 && (size_t)length <= capacity);
    rewind(file);
    void *input = malloc(length), *tree = calloc(1, capacity);
    assert(input && tree && fread(input, 1, length, file) == (size_t)length);
    fclose(file);
    assert(!fdt_check_full(input, length));
    assert(!fdt_open_into(input, tree, capacity));
    free(input);
    return tree;
}

static int probe_unchanged(void *target, const void *source, int expected)
{
    size_t capacity = fdt_totalsize(target);
    void *before = malloc(capacity);
    assert(before);
    memcpy(before, target, capacity);
    int result = apple_j713_import_fdt(target, source);
    assert(result == expected && !memcmp(before, target, capacity));
    free(before);
    return result;
}

/* Invented test release slots; these bytes never leave this host process. */
static int match_synthetic_cpus(void *runtime, const void *os)
{
    int node = fdt_path_offset(runtime, "/cpus");
    assert(node >= 0 && !fdt_del_node(runtime, node));
    int cpus = fdt_add_subnode(runtime, 0, "cpus");
    assert(cpus >= 0 && !fdt_setprop_u32(runtime, cpus, "#address-cells", 2));
    assert(!fdt_setprop_u32(runtime, cpus, "#size-cells", 0));
    int os_cpus = fdt_path_offset(os, "/cpus"), child, count = 0;
    assert(os_cpus >= 0);
    fdt_for_each_subnode(child, os, os_cpus) {
        const char *name = fdt_get_name(os, child, NULL);
        if (strncmp(name, "cpu@", 4))
            continue;
        int len;
        const void *reg = fdt_getprop(os, child, "reg", &len);
        assert(reg && len == 8 && count < 32);
        node = fdt_add_subnode(runtime, cpus, name);
        assert(node >= 0 && !fdt_setprop(runtime, node, "reg", reg, len));
        assert(!fdt_setprop_u64(runtime, node, "cpu-release-addr",
                               count ? 0x900000000ULL + count * 0x4000 : 0));
        count++;
    }
    assert(count > 0);
    return count;
}

static void check_static_policy(const void *before, const void *after)
{
    int node = -1, depth = 0;
    while ((node = fdt_next_node(before, node, &depth)) >= 0) {
        char path[1024];
        assert(!fdt_get_path(before, node, path, sizeof(path)));
        int target = fdt_path_offset(after, path), property;
        assert(target >= 0);
        fdt_for_each_property_offset(property, before, node) {
            int length, after_length;
            const struct fdt_property *value = fdt_get_property_by_offset(before, property, &length);
            assert(value);
            const char *name = fdt_string(before, fdt32_to_cpu(value->nameoff));
            bool policy_node = strstr(path, "/power-management@") || strstr(path, "/pinctrl@") || !strcmp(path, "/soc/pmgr");
            if (!policy_node && strcmp(name, "power-domains") && strcmp(name, "clocks") &&
                strncmp(name, "pinctrl-", 8))
                continue;
            const void *other = fdt_getprop(after, target, name, &after_length);
            assert(other && length == after_length && !memcmp(value->data, other, length));
        }
    }
}

static void check_memory_references(const void *tree)
{
    int node = -1, depth = 0, length;
    while ((node = fdt_next_node(tree, node, &depth)) >= 0) {
        const fdt32_t *refs = fdt_getprop(tree, node, "memory-region", &length);
        if (!refs)
            continue;
        assert(length % 4 == 0);
        for (int i = 0; i < length / 4; i++)
            assert(fdt_node_offset_by_phandle(tree, fdt32_to_cpu(refs[i])) >= 0);
    }
}

int main(int argc, char **argv)
{
    assert(argc == 5 && strlen(argv[4]) == 40);
    for (int i = 0; i < 40; i++)
        assert((argv[4][i] >= '0' && argv[4][i] <= '9') || (argv[4][i] >= 'a' && argv[4][i] <= 'f'));
    void *target = load_tree(argv[1], 1024 * 1024);
    void *runtime = load_tree(argv[2], J713_FDT_MAX_SOURCE);
    assert(!fdt_node_check_compatible(target, 0, "apple,j713"));
    assert(!fdt_node_check_compatible(target, 0, "apple,t8132"));
    int chosen = fdt_path_offset(target, "/chosen");
    assert(chosen >= 0 && !fdt_getprop(target, chosen, J713_FDT_SOURCE, NULL));
    assert(!fdt_getprop(target, chosen, J713_FDT_COMPLETE, NULL));
    assert(probe_unchanged(target, runtime, 0) == 0);
    assert(!fdt_setprop_string(target, chosen, J713_FDT_SOURCE, argv[4]));
    size_t used = fdt_off_dt_strings(target) + fdt_size_dt_strings(target);
    size_t capacity = (used + 0x40000 + 4095) & ~(size_t)4095;
    assert(capacity <= 1024 * 1024);
    fdt_set_totalsize(target, capacity);
    assert(!fdt_check_full(target, capacity));
    assert(probe_unchanged(target, NULL, -EINVAL) == -EINVAL);
    void *wrong = malloc(J713_FDT_MAX_SOURCE);
    assert(wrong && !fdt_open_into(runtime, wrong, J713_FDT_MAX_SOURCE));
    assert(!fdt_setprop_string(wrong, 0, "compatible", "apple,j715"));
    assert(probe_unchanged(target, wrong, -EINVAL) == -EINVAL);
    free(wrong);
    /* Save the prepared static input, never the result containing synthetic addresses. */
    FILE *file = fopen(argv[3], "wb");
    assert(file && fwrite(target, 1, capacity, file) == capacity && !fclose(file));
    void *before = malloc(capacity), *scratch = malloc(capacity);
    assert(before && scratch);
    memcpy(before, target, capacity);
    int generic = apple_j713_import_fdt(target, runtime);
    assert(generic == 1 || (generic < 0 && !memcmp(before, target, capacity)));
    memcpy(target, before, capacity);
    int cpu_count = match_synthetic_cpus(runtime, before);
    void *fault = malloc(J713_FDT_MAX_SOURCE), *runtime_before = malloc(J713_FDT_MAX_SOURCE);
    assert(fault && runtime_before);
    memcpy(runtime_before, runtime, J713_FDT_MAX_SOURCE);
    memcpy(fault, runtime, J713_FDT_MAX_SOURCE);
    int cpus = fdt_path_offset(fault, "/cpus"), cpu = fdt_first_subnode(fault, cpus);
    assert(cpu >= 0 && !fdt_del_node(fault, cpu));
    assert(probe_unchanged(target, fault, -EINVAL) == -EINVAL);
    memcpy(fault, runtime, J713_FDT_MAX_SOURCE);
    cpus = fdt_path_offset(fault, "/cpus");
    cpu = fdt_first_subnode(fault, cpus);
    assert(cpu >= 0 && !fdt_setprop_u64(fault, cpu, "cpu-release-addr", 1));
    assert(probe_unchanged(target, fault, -EINVAL) == -EINVAL);
    int result = apple_j713_import_fdt(target, runtime);
    assert(result == 1);
    check_static_policy(before, target);
    check_memory_references(target);
    assert(!fdt_getprop(target, fdt_path_offset(target, "/chosen"), J713_FDT_COMPLETE, NULL));
    int reservations = fdt_num_mem_rsv(target);
    assert(apple_j713_import_fdt(target, runtime) == 1);
    assert(fdt_num_mem_rsv(target) == reservations);
    check_static_policy(before, target);
    check_memory_references(target);
    assert(!memcmp(runtime, runtime_before, J713_FDT_MAX_SOURCE));
    memcpy(scratch, before, capacity);
    /* Diagnostic stages on disposable bytes only, after calling the real importer. */
    const char *failed = "none";
    int stage = 0;
#define CHECK_STAGE(fn) do { if (!stage) { stage = fn(scratch, runtime); if (stage) failed = #fn; } } while (0)
    CHECK_STAGE(j713_reservations);
    CHECK_STAGE(j713_cpus);
    CHECK_STAGE(j713_devices);
    CHECK_STAGE(j713_bluetooth);
    printf("{\"static_capacity\":%zu,\"generic_import_return\":%d,\"synthetic_cpu_count\":%d,\"synthetic_import_return\":%d,"
           "\"first_diagnostic_failure\":\"%s\",\"diagnostic_return\":%d,"
           "\"rejection_controls_preserved_destination\":true,\"static_policy_preserved\":true,"
           "\"memory_references_resolve\":true,\"repeat_import_succeeded\":true,"
           "\"runtime_source_unchanged\":true}\n", capacity, generic, cpu_count, result, failed, stage);
    return 0;
}
