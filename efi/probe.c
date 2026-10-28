/* Standalone, read-only ARM64 EFI protocol probe. No OS launch or disk APIs. */
#include "abi.h"

static void say(SYSTEM *system, const char *message)
{
    U16 buffer[128];
    UINTN count = 0;
    while (message[count] && count < 125) {
        buffer[count] = (U8)message[count];
        count++;
    }
    buffer[count++] = '\r';
    buffer[count++] = '\n';
    buffer[count] = 0;
    system->output->output(system->output, buffer);
}

STATUS efi_main(void *image, SYSTEM *system)
{
    (void)image;
    if (!system || system->header.signature != 0x5453595320494249ULL ||
        system->header.size < sizeof(SYSTEM) || !system->output || !system->output->output ||
        !system->boot || system->boot->header.signature != 0x56524553544f4f42ULL ||
        system->boot->header.size < sizeof(BOOT) || !system->boot->locate)
        return ERROR(2);
    say(system, "PRE_ASAHI_EFI_PROBE_STARTED");
    /* Exact protocol GUID used by the selected U-Boot, not a different DT protocol. */
    GUID guid = {0xe617d64c, 0xfe08, 0x46da, {0xf4,0xdc,0xbb,0xd5,0x87,0x0c,0x73,0x00}};
    FIXUP *protocol = 0;
    STATUS result = system->boot->locate(&guid, 0, (void **)&protocol);
    if (result == ERROR(14)) {
        say(system, "PRE_ASAHI_DT_FIXUP_ABSENT");
        say(system, "PRE_ASAHI_NO_LINUX_LAUNCH");
        return result;
    }
    if (result || !protocol || !protocol->fixup) {
        say(system, "PRE_ASAHI_DT_FIXUP_LOOKUP_ERROR");
        return result ? result : ERROR(2);
    }
    if (protocol->revision != 0x10000) {
        say(system, "PRE_ASAHI_DT_FIXUP_REVISION_UNSUPPORTED");
        return ERROR(3);
    }
    say(system, "PRE_ASAHI_DT_FIXUP_AVAILABLE");
#ifndef PRE_ASAHI_LAUNCH_TEST
    say(system, "PRE_ASAHI_NO_LINUX_LAUNCH");
#endif
    /* Discovery only: do not call Fixup, install tables, or start another image. */
    return 0;
}
