# goodchars = (
#     "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ,.<>[]1234567890-=!@#$%^&*()_+"
# )


def validate_string(string: str, minlength=8, maxlength=48) -> str | None:
    # r = re.search(r"(?![A-Za-z0-9._=!@#$%^&*()+-])", string, re.RegexFlag.I)
    # r = None
    # for char in string:
    #     if char not in goodchars:
    #         r = char
    #         break
    # if r is not None:
    #     return f"{string} contains invalid characters ({r})! Can only be comprised of these characters: {goodchars}"
    if len(string) < minlength:
        return f"{string} too short! Should be at least {minlength} characters!"
    if len(string) > maxlength:
        return f"{string} too long! Should be at most {maxlength} characters!"
    return None


def validate_snowflake(snowflake: str) -> bool:
    try:
        x = int(snowflake)
        return True
    except:
        return False


def twofellas(snowflakeone: str, snowflaketwo: str) -> str:
    if int(snowflakeone) > int(snowflaketwo):
        return snowflakeone + snowflaketwo
