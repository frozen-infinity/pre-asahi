#include "../efi/fixup.c"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
static int mode, outstanding, calls;
static STATUS output(TEXT *t, U16 *s) { (void)t; (void)s; return 0; }
static STATUS allocate(U32 type, UINTN size, void **p)
{
    assert(type==2 && size<=2*1024*1024);
    if (mode==4 && outstanding) return ERROR(9);
    *p=calloc(1,size); assert(*p); outstanding++; return 0;
}
static STATUS release(void *p) { assert(p && outstanding); free(p); outstanding--; return 0; }
static STATUS fixup(FIXUP *p, void *dtb, UINTN *size, U32 flags)
{
    (void)p; calls++;
    assert(flags==0 || flags==8 || flags==1); /* No RESERVE or INSTALL calls. */
    if (!flags || flags==8 || be32(dtb)!=0xd00dfeed) return ERROR(2);
    if (*size==sizeof(fixture)) {
        *size=mode==1 ? 4*1024*1024 : 4096;
        if (mode==2) ((U8 *)dtb)[0]=0;
        return ERROR(5);
    }
    if (mode==3) return ERROR(2);
    U8 *b=dtb; b[4]=0; b[5]=0; b[6]=0x10; b[7]=0; return 0;
}
static FIXUP protocol={0x10000,(void *)fixup};
static STATUS locate(GUID *g, void *r, void **p) { (void)g; assert(!r); *p=&protocol; return 0; }
int main(void)
{
    TEXT console={.output=output};
    BOOT boot={.header={.signature=0x56524553544f4f42ULL,.size=sizeof(BOOT)},
               .allocate=allocate,.release=release,.locate=locate};
    SYSTEM system={.header={.signature=0x5453595320494249ULL,.size=sizeof(SYSTEM)},
                   .output=&console,.boot=&boot};
    for (mode=0; mode<5; mode++) {
        calls=0;
        STATUS status=efi_main(0,&system);
        assert((status==0)==(mode==0));
        assert(!outstanding);
        assert(calls==(mode==0 || mode==3 ? 5 : 1));
    }
    return 0;
}
