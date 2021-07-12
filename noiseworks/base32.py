# Miss out i l o u
digits = "0123456789abcdefghjkmnpqrstvwxyz"
normalize = str.maketrans("IiLlOo", "111100")


def base32_to_int(s):
    """Convert a base 32 string to an integer"""
    s = s.translate(normalize)
    decoded = 0
    for c in s:
        decoded = decoded * 32 + digits.index(c)
    return decoded


def int_to_base32(i):
    """Converts an integer to a base32 string"""
    enc = ""
    while i > 0:
        i, mod = divmod(i, 32)
        enc = digits[mod] + enc
    return enc


def bytes_to_base32(b):
    i = int.from_bytes(b, byteorder="big")
    enc = int_to_base32(i)
    return enc


def base32_to_bytes(enc, length=4):
    i = base32_to_int(enc)
    b = i.to_bytes(length, byteorder="big")
    return b
