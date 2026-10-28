/* Independently compiled test consumer. Receives SYSTEM only, no producer buffer. */
#include "table-consumer.h"
GUID pre_asahi_fdt_guid = {0xb1b621d5,0xf19c,0x41a5,{0x83,0x0b,0xd9,0x15,0x2c,0x69,0xaa,0xe0}};
static int equal(const U8 *a, const U8 *b, UINTN size)
{
    for (UINTN i=0; i<size; i++) if (a[i]!=b[i]) return 0;
    return 1;
}
STATUS find_fdt_table(SYSTEM *system, void **tree)
{
    *tree=0;
    if (!system || system->table_count>1024 || (system->table_count && !system->tables)) return ERROR(2);
    CONFIG_TABLE *tables=system->tables;
    int seen=0;
    for (UINTN i=0; i<system->table_count; i++) {
        if (equal((U8 *)&tables[i].guid,(U8 *)&pre_asahi_fdt_guid,sizeof(GUID))) {
            if (seen++ || !tables[i].table) return ERROR(2);
            *tree=tables[i].table;
        }
    }
    return seen ? 0 : ERROR(14);
}
static U32 word(const U8 *p) { return (U32)p[0]<<24 | (U32)p[1]<<16 | (U32)p[2]<<8 | p[3]; }
static int text_is(const U8 *p, UINTN available, const char *s, UINTN length)
{
    return available>=length && equal(p,(const U8 *)s,length);
}
STATUS consume_test_fdt(SYSTEM *system)
{
    void *tree;
    STATUS result=find_fdt_table(system,&tree);
    if (result) return result;
    const U8 *b=tree;
    if (word(b)!=0xd00dfeed) return ERROR(2);
    U32 total=word(b+4), structure=word(b+8), strings=word(b+12);
    U32 strings_size=word(b+32), structure_size=word(b+36);
    if (total<40 || total>2*1024*1024 || word(b+20)!=17 || word(b+24)>17 ||
        structure<40 || (structure&3) || structure>total || structure_size>total-structure ||
        strings<40 || strings>total || strings_size>total-strings) return ERROR(2);
    UINTN pos=structure, end=structure+structure_size;
    U32 depth=0, roots=0, cookies=0;
    while (pos<=end && end-pos>=4) {
        U32 token=word(b+pos); pos+=4;
        if (token==1) { /* FDT_BEGIN_NODE */
            if (!depth && roots++) return ERROR(2);
            if (depth>=64) return ERROR(2);
            depth++;
            while (pos<end && b[pos]) pos++;
            if (pos==end) return ERROR(2);
            pos=(pos+4)&~(UINTN)3;
        } else if (token==2) {
            if (!depth) return ERROR(2);
            depth--;
        } else if (token==3) { /* FDT_PROP */
            if (!depth || end-pos<8) return ERROR(2);
            U32 length=word(b+pos), name=word(b+pos+4); pos+=8;
            if (length>end-pos || name>=strings_size) return ERROR(2);
            UINTN n=name;
            while (n<strings_size && b[strings+n]) n++;
            if (n==strings_size) return ERROR(2);
            const char key[]="pre-asahi,test-cookie", value[]="efi-publication-v1";
            if (depth==1 && text_is(b+strings+name,strings_size-name,key,sizeof(key))) {
                if (cookies++ || length!=sizeof(value) || !text_is(b+pos,length,value,sizeof(value))) return ERROR(2);
            }
            pos=(pos+length+3)&~(UINTN)3;
        } else if (token==9) {
            return !depth && roots==1 && cookies==1 ? 0 : ERROR(2);
        } else if (token!=4) return ERROR(2); /* FDT_NOP */
    }
    return ERROR(2);
}
