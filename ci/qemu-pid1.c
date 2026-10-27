/* CI-only init for QEMU virt. No shell, block access, network or reboot action. */
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/utsname.h>
#include <unistd.h>

int main(void)
{
    struct utsname info;
    char compatible[1024];
    size_t size;
    FILE *file;
    if (getpid() != 1 || mount("proc", "/proc", "proc", 0, NULL) ||
        mount("sysfs", "/sys", "sysfs", 0, NULL) || uname(&info))
        return 1;
    file = fopen("/sys/firmware/devicetree/base/compatible", "rb");
    if (!file)
        return 1;
    size = fread(compatible, 1, sizeof(compatible), file);
    fclose(file);
    int found = 0;
    for (size_t offset = 0; offset < size;) {
        const char *end = memchr(compatible + offset, 0, size - offset);
        if (!end)
            return 1;
        if (strcmp(compatible + offset, "linux,dummy-virt") == 0)
            found = 1;
        offset = (size_t)(end - compatible) + 1;
    }
    if (!found || strcmp(info.machine, "aarch64"))
        return 1;
    puts("CI static diagnostic init; pid=1; platform=linux,dummy-virt");
    printf("Guest release: %s\n", info.release);
    puts("M4AIR_PHASE1_PID1");
    fflush(stdout);
    for (;;)
        pause();
}
