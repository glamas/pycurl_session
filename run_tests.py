# coding: utf-8

import sys
import unittest

TEST_LIST = ["tests.base_test", "tests.response_test", "tests.auth_test"]


def main():
    test_list = []
    test_list += TEST_LIST
    for path in test_list:
        __import__(path, None, None, ["foo"])

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for path in test_list:
        mod_suite = loader.loadTestsFromName(path)
        for some_suite in mod_suite:
            for test in some_suite:
                suite.addTest(test)

    with open('test_report.txt', 'a') as f:
        runner = unittest.TextTestRunner(stream=f, verbosity=2)
        result = runner.run(suite)

    if result.wasSuccessful():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
