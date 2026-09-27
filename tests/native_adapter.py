"""MQL integer ABI for the C++ test harness only; never modifies src/."""
import re

TOKENS = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|\'(?:\\.|[^\'\\])*\'|"(?:\\.|[^"\\])*"|\b(?:unsigned\s+)?long(?:\s+long)?\b|\b(?:ulong|uint)\b')
CONTRACT = r'''
static_assert(sizeof(int)==4 && sizeof(mql_uint)==4);
static_assert(sizeof(mql_long)==8 && sizeof(mql_ulong)==8 && sizeof(datetime)==8);
static_assert(sizeof(void*)==8 && sizeof(double)==8 && sizeof(char16_t)==2);
static_assert(std::is_signed_v<mql_long> && std::is_unsigned_v<mql_ulong>);
inline const bool abi_checked=[](){
 const datetime future=2208988800LL;
 if(future*1000/1000!=future || (mql_ulong(1)<<40)!=1099511627776ULL) std::abort();
 std::tm t{};t.tm_year=140;t.tm_mon=0;t.tm_mday=1;
#ifdef _WIN32
 const auto epoch=_mkgmtime64(&t);
 std::tm back{};if(_gmtime64_s(&back,&epoch)!=0)std::abort();
#else
 const auto epoch=timegm(&t);
 std::tm back{};if(gmtime_r(&epoch,&back)==nullptr)std::abort();
#endif
 if(epoch!=future || back.tm_year!=140 || back.tm_mon!=0 || back.tm_mday!=1)std::abort();
 std::cerr<<"ABI_CONTRACT {\"contract\":\"mql64-v1\",\"native_long\":"<<sizeof(long)
          <<",\"mql_long\":8,\"ulong\":8,\"datetime\":8,\"uint\":4,\"pointer\":8,\"time_2040\":true,\"compiler\":\""<<__VERSION__<<"\"}\n";
 return true;
}();
'''


def prepare(code):
    # System headers are parsed before aliases; token rewriting is restricted to
    # generated MQL/mock/scenario text. Native long long casts remain unchanged.
    includes = re.findall(r'(?m)^#include[^\n]*', code)
    code = re.sub(r'(?m)^#include[^\n]*', '', code)
    types = {'long': 'mql_long', 'ulong': 'mql_ulong', 'uint': 'mql_uint'}
    code = TOKENS.sub(lambda m: types.get(m[0], m[0]), code)
    prefix = '\n'.join(dict.fromkeys(includes + ['#include <cstdint>', '#include <ctime>']))
    prefix += '\nusing mql_long=std::int64_t;using mql_ulong=std::uint64_t;using mql_uint=std::uint32_t;\n'
    return prefix + code + '\n' + CONTRACT
