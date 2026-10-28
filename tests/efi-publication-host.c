#include "../efi/publication.c"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
static SYSTEM *active;
static CONFIG_TABLE entries[2];
static int mode, outstanding, restores;
static U8 prior[40];
static STATUS output(TEXT *t, U16 *s) { (void)t; (void)s; return 0; }
static STATUS allocate(U32 type, UINTN size, void **p)
{
    assert(type==2 && size<=2*1024*1024);
    *p=calloc(1,size); assert(*p); outstanding++; return 0;
}
static STATUS release(void *p)
{
    void *published=0;
    (void)find_fdt_table(active,&published);
    assert(p && p!=published && outstanding); free(p); outstanding--; return 0;
}
static void publish(void *p)
{
    entries[0].guid=pre_asahi_fdt_guid; entries[0].table=p;
    active->tables=entries; active->table_count=p ? 1 : 0;
}
static STATUS install(GUID *g, void *p)
{
    assert(!memcmp(g,&pre_asahi_fdt_guid,sizeof(GUID)));
    restores++;
    if (mode==4) return ERROR(9);
    publish(p); return 0;
}
static STATUS fixup(FIXUP *p, void *dtb, UINTN *size, U32 flags)
{
    (void)p; assert(flags==1 || flags==5);
    if (*size==sizeof(fixture)) { *size=mode==6 ? 4*1024*1024 : 4096; return ERROR(5); }
    assert(flags==5);
    if (mode==1) return ERROR(9);
    U8 *b=dtb; b[4]=0; b[5]=0; b[6]=0x10; b[7]=0;
    publish(dtb);
    if (mode==5) b[4]=0x7f; /* Reject a published header exceeding allocation capacity. */
    if (mode==2) return ERROR(9); /* Model partial publication on failure. */
    if (mode==3) {
        const char cookie[]="efi-publication-v1";
        for (UINTN i=0; i+sizeof(cookie)<=sizeof(fixture); i++)
            if (!memcmp(b+i,cookie,sizeof(cookie))) { b[i]='x'; break; }
    }
    return 0;
}
static FIXUP protocol={0x10000,(void *)fixup};
static STATUS locate(GUID *g, void *r, void **p) { (void)g; assert(!r); *p=&protocol; return 0; }
int main(void)
{
    TEXT console={.output=output};
    BOOT boot={.header={.signature=0x56524553544f4f42ULL,.size=sizeof(BOOT)},
               .allocate=allocate,.release=release,.install_table=install,.locate=locate};
    SYSTEM system={.header={.signature=0x5453595320494249ULL,.size=sizeof(SYSTEM)},
                   .output=&console,.boot=&boot};
    active=&system;
    for (int existing=0; existing<2; existing++) for (mode=0; mode<7; mode++) {
        void *previous=existing ? prior : 0;
        publish(previous); restores=0;
        STATUS status=efi_main(0,&system);
        assert((status==0)==(mode==0));
        void *current=0;
        STATUS found=find_fdt_table(&system,&current);
        if (mode==4) {
            assert(!found && current && current!=previous && outstanding==1);
            publish(previous); free(current); outstanding--;
        } else {
            assert(current==previous && !outstanding);
            assert(restores==((mode==1 || mode==6) ? 0 : 1));
        }
    }
    /* Independent consumer refuses bad/missing/ambiguous tables and malformed data. */
    U8 tree[sizeof(fixture)]; memcpy(tree,fixture,sizeof(tree));
    publish(tree); assert(!consume_test_fdt(&system));
    tree[0]=0; assert(consume_test_fdt(&system));
    memcpy(tree,fixture,sizeof(tree)); tree[36]=0x7f; assert(consume_test_fdt(&system));
    memcpy(tree,fixture,sizeof(tree)); tree[12]=0x7f; assert(consume_test_fdt(&system));
    entries[1]=entries[0]; system.table_count=2; assert(consume_test_fdt(&system));
    system.table_count=1025; assert(consume_test_fdt(&system));
    system.table_count=1; system.tables=0; assert(consume_test_fdt(&system));
    publish(0); assert(consume_test_fdt(&system)==ERROR(14));
    return 0;
}
