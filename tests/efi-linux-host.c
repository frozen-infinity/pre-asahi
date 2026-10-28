#include "../efi/linux-entry.c"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
static SYSTEM *active;
static CONFIG_TABLE table;
static U8 original[40];
static LOADED loaded;
static int mode, allocations, loads, starts, unloads;
static STATUS output(TEXT *t,U16 *s) { (void)t; (void)s; return 0; }
static STATUS allocate(U32 type,UINTN size,void **p) { assert(type==2); *p=calloc(1,size); assert(*p); allocations++; return 0; }
static STATUS release(void *p) { assert(p && p!=table.table); free(p); allocations--; return 0; }
static STATUS install(GUID *g,void *p) { assert(!memcmp(g,&pre_asahi_fdt_guid,sizeof(GUID))); if(mode==4)return ERROR(9); table.table=p; return 0; }
static STATUS fixup(FIXUP *p,void *dtb,UINTN *size,U32 flags) { (void)p; assert(flags==5 && *size>sizeof(test_tree)); table.table=dtb; return mode==5 ? ERROR(9) : 0; }
static FIXUP protocol={0x10000,(void *)fixup};
static STATUS locate(GUID *g,void *r,void **p) { (void)g; assert(!r); *p=&protocol; return 0; }
static STATUS load(U8 policy,void *parent,void *path,void *source,UINTN size,void **child)
{
    assert(!policy && parent==(void *)0xabc && !path && source==(void *)(UINTN)TEST_KERNEL_ADDRESS && size==TEST_KERNEL_SIZE);
    assert((table.table!=original)==TEST_INSTALL); loads++;
    if(mode==1)return ERROR(9);
    *child=(void *)0xbeef; return 0;
}
static STATUS handle(void *child,GUID *g,void **p) { (void)g; assert(child==(void *)0xbeef); if(mode==2)return ERROR(9); *p=&loaded; return 0; }
static STATUS start(void *child,UINTN *size,U16 **data)
{
    assert(child==(void *)0xbeef && !*size && !*data);
    assert(loaded.options_size>2 && ((U16 *)loaded.options)[0]=='c'); starts++; return 0;
}
static STATUS unload(void *child) { assert(child==(void *)0xbeef); unloads++; return mode==3 ? ERROR(9) : 0; }
int main(void)
{
    TEXT console={.output=output};
    BOOT boot={.header={.signature=0x56524553544f4f42ULL,.size=sizeof(BOOT)},.allocate=allocate,
        .release=release,.install_table=install,.locate=locate,.handle_protocol=handle,
        .load_image=load,.start_image=start,.unload_image=unload};
    SYSTEM system={.header={.signature=0x5453595320494249ULL,.size=sizeof(SYSTEM)},.output=&console,.boot=&boot,.table_count=1,.tables=&table};
    active=&system; (void)active; table.guid=pre_asahi_fdt_guid;
    for(mode=0;mode<6;mode++) {
        table.table=original; loads=starts=unloads=allocations=0;
        memset(&loaded,0,sizeof(loaded));
        assert(efi_main((void *)0xabc,&system)); /* Any return fails the Linux test. */
        if(TEST_INSTALL && (mode==3 || mode==4)) {
            assert(allocations==1 && table.table!=original);
            void *retained=table.table; table.table=original; free(retained); allocations--;
        }
        assert(table.table==original && !allocations);
        assert(loads==(TEST_INSTALL && mode==5 ? 0 : 1));
        assert(starts==(mode==1 || mode==2 || (TEST_INSTALL && mode==5) ? 0 : 1));
        assert(unloads==(mode==1 || (TEST_INSTALL && mode==5) ? 0 : 1));
    }
    return 0;
}
