import argparse
import json
import os
import re
import sys

from bs4 import BeautifulSoup
from packaging import version

CUR_PATH = "{0}/".format(os.path.dirname(__file__))

sys.path.append(CUR_PATH)

import pytest_html_merger.version as version_mod

CHECKBOX_REGEX = r"^(?P<num>0|[1-9]\d*) (?P<txt1>.*)"


def merge_html_files(in_path: str, out_path: str, title: str):
    paths = get_html_files(in_path, out_path)
    if not paths:
        raise RuntimeError(f"Unable to find html files in {in_path}")

    assets_dir_path = get_assets_path(in_path)

    first_file = BeautifulSoup("".join(open(paths[0])), features="html.parser")
    paths.pop(0)

    try:
        first_file.find("link").decompose()
    except:
        pass

    if assets_dir_path:
        with open(os.path.join(assets_dir_path, "style.css"), "r") as f:
            content = f.read()

            head = first_file.head
            head.append(first_file.new_tag("style", type="text/css"))
            head.style.append(content)

    h = first_file.find("h1")
    h.string = title or os.path.basename(out_path)

    ps = first_file.find_all("p")
    pytest_version = ps[0].text.split(" ")[-1]
    ps.pop(0)

    cb_types = {
        "passed": [0, ""],
        "skipped": [0, ""],
        "failed": [0, ""],
        "error": [0, ""],
        "xfailed": [0, ""],
        "xpassed": [0, ""],
    }

    html_ver = version.parse(pytest_version)
    if html_ver >= version.parse("4.0.0rc"):
        cb_types["rerun"] = [0, ""]

    for cb_type in cb_types:
        cb_val = get_checkbox_value(first_file, cb_type)
        cb_types[cb_type][0] = cb_val[0]
        cb_types[cb_type][1] = cb_val[1]

    dur, test_count, fp = get_test_count_and_duration(ps)

    if html_ver < version.parse("4.0.0rc"):
        t = first_file.find("table", {"id": "results-table"})
    else:
        f_json_blob = first_file.find("div", {"id": "data-container"}).get(
            "data-jsonblob"
        )
        # Convert the JSON string into a dictionary
        f_data_dict = json.loads(f_json_blob)

    for path in paths:
        cur_file = BeautifulSoup("".join(open(path)), features="html.parser")

        if html_ver < version.parse("4.0.0rc"):
            tbody_res = cur_file.find_all("tbody", {"class": "results-table-row"})
            for elm in tbody_res:
                t.append(elm)
        else:
            f_json_blob = cur_file.find("div", {"id": "data-container"}).get(
                "data-jsonblob"
            )
            # Convert the JSON string into a dictionary
            c_data_dict = json.loads(f_json_blob)

            f_data_dict["tests"].update(c_data_dict["tests"])

        p_res = cur_file.find_all("p")
        _dur, _test_count, _ = get_test_count_and_duration(p_res)
        dur += _dur
        test_count += _test_count

        for cb_type in cb_types:
            tmp = get_checkbox_value(cur_file, cb_type)
            cb_types[cb_type][0] += tmp[0]

        fp.string = f"{test_count} tests ran in {dur} seconds"

    if html_ver >= version.parse("4.0.0rc"):
        first_file.find("div", {"id": "data-container"})["data-jsonblob"] = json.dumps(
            f_data_dict
        )

    for cb_type in cb_types:
        set_checkbox_value(first_file, cb_type, cb_types[cb_type])

    with open(out_path, "w") as f:
        f.write(str(first_file))


def get_test_count_and_duration(ps):
    test_count = 0
    dur = 0
    fp = None

    for p in ps:
        if re.search(r"test.* took ", p.text):
            tmp = p.text.split(" ")
            test_count = int(tmp[0])

            if "ms." in tmp:
                dur = int(tmp[3]) / 1000
            else:
                hours, minutes, seconds = map(int, tmp[3][:-1].split(":"))
                dur = hours * 3600 + minutes * 60 + seconds

            fp = p

            break

        elif " tests ran" in p.text:
            tmp = p.text.split(" ")
            test_count = int(tmp[0])
            dur = float(tmp[4])
            fp = p

            break

    return dur, test_count, fp


def set_checkbox_value(root_soap, cb_type, val):
    elem = root_soap.find("span", {"class": cb_type})
    match = re.search(CHECKBOX_REGEX, elem.text)
    if match is None:
        raise RuntimeError(f"{cb_type} <span> not found")

    elem.string = f"{val[0]} {val[1]}"

    elem = root_soap.find("input", {"data-test-result": cb_type})
    if val[0] != 0:
        del elem["disabled"]
        del elem["hidden"]


def get_checkbox_value(root_soap, cb_type):
    elem = root_soap.find("span", {"class": cb_type})
    match = re.search(CHECKBOX_REGEX, elem.text)
    if match is None:
        raise RuntimeError(f"{cb_type} <span> not found")

    gdict = match.groupdict()

    return int(gdict["num"]), gdict["txt1"]


def get_html_files(path, output_file_path):
    onlyfiles = []

    for file in os.listdir(path):
        _, ext = os.path.splitext(file)
        res = os.path.join(path, file)
        if os.path.isfile(res) and ext == ".html":
            if os.path.abspath(output_file_path) == res:
                continue

            content = BeautifulSoup("".join(open(res)), features="html.parser").find(
                "p"
            )
            if content and "Report generated on " in content.text:
                onlyfiles.append(res)

    return sorted(onlyfiles, reverse=True)


def get_assets_path(path):
    _dirs = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
    return os.path.join(path, "assets") if "assets" in _dirs else None


def parse_user_commands(command_line):
    parser = argparse.ArgumentParser(
        description="Merges .html reports from created by pytest-html plugin."
        "Will assume css is embedded in the reports. If this is not the case, "
        "Please make sure that you have 'assets' directory inside input directory "
        "which contains css files generated by pytest-html."
    )

    parser.add_argument(
        "--version", "-v", action="version", version=version_mod.version
    )

    parser.add_argument(
        "-i",
        "--input",
        default=os.getcwd(),
        help="directory containing the input .html files (default is cwd)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=os.path.join(os.getcwd(), "merged.html"),
        help="path to create output file (default is ./merged.html)",
    )
    parser.add_argument(
        "-t",
        "--title",
        default=None,
        help="title of the merged report (default is output file name)",
    )

    args = parser.parse_args(command_line)

    return args


def main(command_line=None):
    args = parse_user_commands(command_line)

    merge_html_files(str(args.input), str(args.output), args.title)


if __name__ == "__main__":
    main()
