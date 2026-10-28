/* QEMU-only launcher. Generated inputs bind this executable to one emulated test. */
#define PRE_ASAHI_LAUNCH_TEST
#define efi_main discovery_main
#include "probe.c"
#undef efi_main
#include "table-consumer.h"
#include "linux-test-input.h"
typedef struct {
    U32 revision;
    void *parent, *system, *device, *path, *reserved;
    U32 options_size;
    void *options;
    void *image_base;
    U64 image_size;
    U32 code_type, data_type;
    void *unload;
} LOADED;
_Static_assert(__builtin_offsetof(LOADED, options_size)==48, "EFI loaded options size offset");
_Static_assert(__builtin_offsetof(LOADED, options)==56, "EFI loaded options pointer offset");
typedef STATUS (*CALL_FIXUP)(FIXUP *, void *, UINTN *, U32);
static U32 word(const U8 *p) { return (U32)p[0]<<24 | (U32)p[1]<<16 | (U32)p[2]<<8 | p[3]; }
STATUS efi_main(void *image, SYSTEM *system)
{
    STATUS result=discovery_main(image,system);
    if (result) return result;
    BOOT *boot=system->boot;
    if (!boot->allocate || !boot->release || !boot->install_table || !boot->handle_protocol ||
        !boot->load_image || !boot->start_image || !boot->unload_image) return ERROR(2);
    void *previous=0, *child=0;
    U8 *tree=0;
    result=find_fdt_table(system,&previous);
    if (result) return result; /* Outer bootefi must have supplied a full QEMU tree. */
    GUID loaded_guid={0x5b1b31a1,0x9562,0x11d2,{0x8e,0x3f,0x00,0xa0,0xc9,0x69,0x72,0x3b}};
    if (TEST_INSTALL) {
        GUID guid={0xe617d64c,0xfe08,0x46da,{0xf4,0xdc,0xbb,0xd5,0x87,0x0c,0x73,0x00}};
        FIXUP *protocol=0;
        if (boot->locate(&guid,0,(void **)&protocol) || !protocol || !protocol->fixup || protocol->revision!=0x10000)
            return ERROR(2);
        UINTN capacity=sizeof(test_tree)+65536, size=capacity;
        if (capacity>2*1024*1024 || boot->allocate(2,capacity,(void **)&tree) || !tree) return ERROR(9);
        for (UINTN i=0; i<sizeof(test_tree); i++) tree[i]=test_tree[i];
        CALL_FIXUP call=(CALL_FIXUP)protocol->fixup;
        result=call(protocol,tree,&size,5); /* APPLY | INSTALL; not RESERVE. */
        if (result || size>capacity || word(tree+4)>capacity) goto returned;
        void *current=0;
        if (find_fdt_table(system,&current) || current!=tree) goto returned;
        say(system,"PRE_ASAHI_LINUX_TREE_PUBLISHED");
    } else {
        say(system,"PRE_ASAHI_LINUX_CONTROL_TREE");
    }
    /* This address/length is generated only after exact artifact and PE checks. */
    result=boot->load_image(0,image,0,(void *)(UINTN)TEST_KERNEL_ADDRESS,TEST_KERNEL_SIZE,&child);
    if (result || !child) goto returned;
    LOADED *loaded=0;
    result=boot->handle_protocol(child,&loaded_guid,(void **)&loaded);
    if (result || !loaded) goto returned;
    static U16 options[]={'c','o','n','s','o','l','e','=','t','t','y','A','M','A','0',' ',
        'r','d','i','n','i','t','=','/','i','n','i','t',' ',
        'l','o','g','l','e','v','e','l','=','7',' ', 'p','a','n','i','c','=','-','1',0};
    loaded->options=options;
    loaded->options_size=sizeof(options);
    say(system,"PRE_ASAHI_STARTING_LINUX_EFI");
    UINTN exit_size=0;
    U16 *exit_data=0;
    result=boot->start_image(child,&exit_size,&exit_data);
    /* Success never returns after Linux exits boot services. Any return fails this test. */
    (void)result;
    if (exit_data) boot->release(exit_data);
returned:;
    /* Only reachable while boot services remain available. */
    say(system,"PRE_ASAHI_LINUX_EFI_RETURNED");
    if (child && boot->unload_image(child)) return ERROR(2);
    if (tree) {
        void *current=0;
        if (boot->install_table(&pre_asahi_fdt_guid,previous) ||
            find_fdt_table(system,&current) || current!=previous) return ERROR(2);
        if (boot->release(tree)) return ERROR(2);
    }
    return ERROR(2);
}
