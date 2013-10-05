import lxml.etree
from time import strptime
from parse import fetch_page, BASE_URL


def is_latest_present(latest):
    """
    Check input file to see if a HN link is already present.
    Returns True if present, False if not.
    """
    with open('input', 'r') as f:
        for inputline in f.readlines():
            if latest == inputline:
                return True
    return False


def get_latest():
    """
    Find latest "Who is hiring?" link from HN.
    Return a string formatted for input file "itemid year-month\n"
    """
    response = fetch_page(BASE_URL + 'submitted?id=whoishiring')
    parser = lxml.etree.HTMLParser()
    tree = lxml.etree.fromstring(response, parser)
    # get "Who is hiring?" links from main page
    # covers a year so no real need to go further back
    query = tree.xpath("//a[starts-with(.,'Ask HN: Who is hiring?')]")

    latest = query[0]
    start = latest.text.find('(') + 1
    end = latest.text.find(')')

    # strip link to itemid, and convert date to format used in input file
    datetext = latest.text[start:end]
    dateobj = strptime(datetext, '%B %Y')
    link = latest.xpath('@href')[0].partition('item?id=')[-1]
    output = link + ' ' + str(dateobj.tm_year) \
        + '-' + str(dateobj.tm_mon) + '\n'
    return output


def write_latest(latest, filename='input'):
    """
    Append latest HN "Who is hiring?" itemid and date to input file.
    """
    with open('input', 'a') as f:
        f.write(latest)


def main():
    """
    Get latest HN "Who is hiring?" link, check if already in input file.
    Append it to file if not.
    """
    latest = get_latest()
    if is_latest_present(latest):
        print("Latest link already present in input.")
    else:
        print("Appending latest link to input.")
        write_latest(latest)

if __name__ == '__main__':
    main()
