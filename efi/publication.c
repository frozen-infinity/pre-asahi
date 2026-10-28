/* QEMU-only table publication and rollback. Never launch an OS. */
#define efi_main discovery_main
#include "probe.c"
#undef efi_main
#include "synthetic-fdt.h"
#include "table-consumer.h"
typedef STATUS (*FIXUP_CALL)(FIXUP *, void *, UINTN *, U32);
static void copy_fixture(U8 *p) { for (UINTN i=0; i<sizeof(fixture); i++) p[i]=fixture[i]; }
STATUS efi_main(void *image, SYSTEM *system)
{
    STATUS result=discovery_main(image,system);
    if (result) return result;
    BOOT *boot=system->boot;
    if (!boot->allocate || !boot->release || !boot->install_table) return ERROR(2);
    void *previous=0;
    result=find_fdt_table(system,&previous);
    if (result && result!=ERROR(14)) return result;
    GUID guid={0xe617d64c,0xfe08,0x46da,{0xf4,0xdc,0xbb,0xd5,0x87,0x0c,0x73,0x00}};
    FIXUP *protocol=0;
    if (boot->locate(&guid,0,(void **)&protocol) || !protocol || !protocol->fixup || protocol->revision!=0x10000) return ERROR(2);
    FIXUP_CALL call=(FIXUP_CALL)protocol->fixup;
    U8 *small=0, *buffer=0;
    UINTN size=sizeof(fixture);
    if (boot->allocate(2,size,(void **)&small) || !small) return ERROR(9);
    copy_fixture(small);
    result=ERROR(2);
    /* APPLY only for sizing; INSTALL is requested only with sufficient space. */
    if (call(protocol,small,&size,1)!=ERROR(5) || size<=sizeof(fixture) || size>2*1024*1024) goto done;
    if (boot->allocate(2,size,(void **)&buffer) || !buffer) goto done;
    UINTN capacity=size;
    copy_fixture(buffer);
    if (call(protocol,buffer,&size,5)) goto done; /* APPLY | INSTALL, never RESERVE. */
    U32 total=(U32)buffer[4]<<24 | (U32)buffer[5]<<16 | (U32)buffer[6]<<8 | buffer[7];
    if (size>capacity || total<40 || total>capacity) goto done;
    void *published=0;
    if (find_fdt_table(system,&published) || published!=buffer) goto done;
    say(system,"PRE_ASAHI_TABLE_PUBLISHED");
    /* This consumer discovers the tree from the EFI system table, not our pointer. */
    if (consume_test_fdt(system)) goto done;
    say(system,"PRE_ASAHI_TABLE_CONSUMER_PASS");
    result=0;
done:;
    /* Even a failed call could have changed the table: inspect before releasing. */
    void *current=0;
    STATUS observed=find_fdt_table(system,&current);
    if ((observed && observed!=ERROR(14)) || current!=previous) {
        if (boot->install_table(&pre_asahi_fdt_guid,previous)) result=ERROR(2);
        observed=find_fdt_table(system,&current);
        if ((observed && observed!=ERROR(14)) || current!=previous) {
            /* Never free memory that may still be published. VM teardown reclaims it. */
            say(system,"PRE_ASAHI_PUBLICATION_RETAINED");
            if (boot->release(small)) result=ERROR(2);
            return ERROR(2);
        }
    }
    if (buffer && boot->release(buffer)) result=ERROR(2);
    if (boot->release(small)) result=ERROR(2);
    say(system,"PRE_ASAHI_TABLE_RESTORED");
    say(system,result ? "PRE_ASAHI_PUBLICATION_FAILED" : "PRE_ASAHI_PUBLICATION_PASS");
    say(system,"PRE_ASAHI_NO_LINUX_LAUNCH");
    return result;
}
