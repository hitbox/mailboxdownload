def parse_wgl_table(report_table_soup):
    """
    """
    rows = iter(report_table_soup('tr'))
    header = next(rows)
    field_names = [td.get_text(strip=True) for td in header('td')]
    for row in rows:
        strings = [td.get_text(strip=True) for td in row('td')]
        data = dict(zip(field_names, strings, strict=True))
        yield data
