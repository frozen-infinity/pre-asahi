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
    int result = apple_j713_import_fdt(target, runtime);
    assert(result == 1 || (result < 0 && !memcmp(before, target, capacity)));
    memcpy(scratch, before, capacity);
    /* Diagnostic stages on disposable bytes only, after calling the real importer. */
    const char *failed = "none";
    int stage = 0;
#define CHECK_STAGE(fn) do { if (!stage) { stage = fn(scratch, runtime); if (stage) failed = #fn; } } while (0)
    CHECK_STAGE(j713_reservations);
    CHECK_STAGE(j713_cpus);
    CHECK_STAGE(j713_devices);
    CHECK_STAGE(j713_bluetooth);
    printf("{\"static_capacity\":%zu,\"synthetic_import_return\":%d,"
           "\"first_diagnostic_failure\":\"%s\",\"diagnostic_return\":%d,"
           "\"rejection_preserved_destination\":%s}\n", capacity, result, failed, stage,
           result < 0 ? "true" : "false");
    return 0;
}
