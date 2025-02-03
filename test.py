import pefile

def check_dll_architecture(dll_path):
    pe = pefile.PE(dll_path)
    if pe.FILE_HEADER.Machine == 0x014c:
        return "32-bit"
    elif pe.FILE_HEADER.Machine == 0x8664:
        return "64-bit"
    else:
        return "Unknown architecture"

dll_path = "src/GLedApi.dll"  # Replace with the actual path to your DLL
architecture = check_dll_architecture(dll_path)
print(f"The DLL is {architecture}.")