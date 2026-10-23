"""Days as numbers, for dates far before year 1 (Python's datetime stops there): a day is its count from 1970-01-01 in
the proleptic Gregorian calendar, a year astronomical (0 is 1 BC, -479 is 480 BC) -- written as ISO 8601 does it,
"-0479-08-06". (Hinnant's days_from_civil / civil_from_days; Richards' algorithm for the Julian calendar.)"""


def days(y, m=1, d=1):
    """(year, month, day) -> the day's number"""
    y -= m <= 2
    era = y // 400                                           # (Python's // floors: no C-style adjustment for y < 0)
    yoe = y - era * 400
    doy = (153 * (m - 3 if m > 2 else m + 9) + 2) // 5 + d - 1
    return era * 146097 + yoe * 365 + yoe // 4 - yoe // 100 + doy - 719468


def civil(n):
    """a day's number -> (year, month, day)"""
    n += 719468
    era = n // 146097
    doe = n - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d, m = doy - (153 * mp + 2) // 5 + 1, mp + 3 if mp < 10 else mp - 9
    return yoe + era * 400 + (m <= 2), m, d


def julian(n):
    """a day's number -> (year, month, day) in the Julian calendar"""
    j = n + 2440588 + 32082                                  # (its Julian day number, then counted from 4801 BC)
    b = (4 * j + 3) // 1461
    e = j - 1461 * b // 4
    m = (5 * e + 2) // 153
    return b - 4800 + (m + 3 > 12), (m + 2) % 12 + 1, e - (153 * m + 2) // 5 + 1


def year_text(y):
    return f"-{-y:04d}" if y < 0 else f"{y:04d}"


def iso(n):
    """a day's number -> "YYYY-MM-DD" (a year before 1 with its minus)"""
    y, m, d = civil(n)
    return f"{year_text(y)}-{m:02d}-{d:02d}"
