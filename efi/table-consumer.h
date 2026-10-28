#ifndef PRE_ASAHI_TABLE_CONSUMER_H
#define PRE_ASAHI_TABLE_CONSUMER_H
#include "abi.h"
extern GUID pre_asahi_fdt_guid;
STATUS find_fdt_table(SYSTEM *system, void **tree);
STATUS consume_test_fdt(SYSTEM *system);
#endif
