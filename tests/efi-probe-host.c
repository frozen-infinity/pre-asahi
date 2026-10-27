/* Host tests of the same freestanding EFI entry point; services are substitutes. */
#include "../efi/probe.c"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static char log_text[4096];
static UINTN position;
static STATUS lookup_result;
static FIXUP available;
static int calls;
static STATUS output(TEXT *text, U16 *message)
{
    (void)text;
    for (UINTN i = 0; message[i]; i++) {
        assert(message[i] < 128 && position + 1 < sizeof(log_text));
        log_text[position++] = (char)message[i];
    }
    log_text[position] = 0;
    return 0;
}
static STATUS locate(GUID *guid, void *registration, void **interface)
{
    GUID wanted = {0xe617d64c, 0xfe08, 0x46da, {0xf4,0xdc,0xbb,0xd5,0x87,0x0c,0x73,0x00}};
    assert(!memcmp(guid, &wanted, sizeof(wanted)) && !registration);
    calls++;
    *interface = lookup_result ? NULL : &available;
    return lookup_result;
}
static void reset(void)
{
    position = calls = 0;
    log_text[0] = 0;
    available.revision = 0x10000;
    /* A non-null sentinel, not a callable function: the probe must never invoke it. */
    available.fixup = (void *)(UINTN)1;
}

int main(void)
{
    TEXT console = {.output = output};
    BOOT boot = {.header = {.signature = 0x56524553544f4f42ULL, .size = sizeof(BOOT)}, .locate = locate};
    SYSTEM system = {.header = {.signature = 0x5453595320494249ULL, .size = sizeof(SYSTEM)},
                     .output = &console, .boot = &boot};
    reset(); lookup_result = ERROR(14);
    assert(efi_main(NULL, &system) == ERROR(14));
    assert(calls == 1 && strstr(log_text, "PRE_ASAHI_DT_FIXUP_ABSENT"));
    assert(strstr(log_text, "PRE_ASAHI_NO_LINUX_LAUNCH"));
    reset(); lookup_result = 0;
    assert(!efi_main(NULL, &system));
    assert(calls == 1 && strstr(log_text, "PRE_ASAHI_DT_FIXUP_AVAILABLE"));
    assert(strstr(log_text, "PRE_ASAHI_NO_LINUX_LAUNCH"));
    reset(); available.revision = 0x20000;
    assert(efi_main(NULL, &system) == ERROR(3));
    assert(strstr(log_text, "REVISION_UNSUPPORTED"));
    reset(); available.fixup = NULL;
    assert(efi_main(NULL, &system) == ERROR(2));
    assert(strstr(log_text, "LOOKUP_ERROR"));
    reset(); lookup_result = ERROR(7);
    assert(efi_main(NULL, &system) == ERROR(7));
    assert(strstr(log_text, "LOOKUP_ERROR"));
    reset(); system.header.signature = 0;
    assert(efi_main(NULL, &system) == ERROR(2) && !calls && !position);
    assert(efi_main(NULL, NULL) == ERROR(2));
    puts("EFI_PROBE_HOST_BRANCHES_PASS");
    return 0;
}
