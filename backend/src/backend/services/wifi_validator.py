ALLOWED_BSSIDS = [
    "F4-27-56-7C-2D-9F"
]

def validate_wifi(bssid):

    print("Received:", repr(bssid))
    print("Allowed :", repr(ALLOWED_BSSIDS[0]))

    # result = bssid.upper() in ALLOWED_BSSIDS
    if bssid == ALLOWED_BSSIDS[0]:
        print("Exact Match Found")
        result = True
    else:
        print("No Match Found")
        result = False

    print("Match Result:", result)

    return result