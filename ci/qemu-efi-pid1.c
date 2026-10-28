/* Diskless CI guest: require PID 1, EFI boot and the private tree's fresh cookie. */
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/utsname.h>
#include <unistd.h>
#include "linux-test-cookie.h"
static int read_exact(const char *path, const char *expected, size_t length)
{
    char data[128];
    FILE *f=fopen(path,"rb");
    if (!f) return 0;
    size_t n=fread(data,1,sizeof(data),f);
    int ok=!ferror(f) && n==length && !memcmp(data,expected,length);
    fclose(f); return ok;
}
int main(void)
{
    struct utsname info;
    int ok=getpid()==1 && !mount("proc","/proc","proc",0,NULL) &&
        !mount("sysfs","/sys","sysfs",0,NULL) && !uname(&info) &&
        !strcmp(info.machine,"aarch64") &&
        read_exact("/sys/firmware/efi/fw_platform_size","64\n",3);
    puts("PRE_ASAHI_LINUX_EFI_PID1_REACHED");
    if (ok && read_exact("/sys/firmware/devicetree/base/pre-asahi,test-cookie", TEST_COOKIE, sizeof(TEST_COOKIE))) {
        puts("PRE_ASAHI_LINUX_EFI_COOKIE=" TEST_COOKIE);
        puts("PRE_ASAHI_LINUX_EFI_FW_BITS=64");
        puts("PRE_ASAHI_LINUX_EFI_PID1_PASS");
    } else {
        puts("PRE_ASAHI_LINUX_EFI_PID1_REJECTED");
    }
    fflush(stdout);
    for (;;) pause();
}
