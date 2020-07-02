import datetime
import unittest
import os
import shutil
import gzip
from collections import namedtuple

from log_analyzer import read_conf, search_last_log_file, read_log, formation_report, write_to_file


class TestReadConf(unittest.TestCase):
    def setUp(self):
        self.config = {
            "REPORT_SIZE": 1000,
            "REPORT_DIR": "./reports_test_default",
            "LOG_DIR": "./log_test_default",
            "LOG_DIR_CURRENT_SCRIPT": "./log_log_test_default"
        }
        os.makedirs('config_test')
        with open(os.path.join('config_test', 'config.conf'), 'w') as f:
            f.writelines('REPORT_SIZE: 123\n')
            f.writelines('REPORT_DIR: ./reports_test\n')
            f.writelines('LOG_DIR: ./log_test\n')

    def tearDown(self):
        shutil.rmtree('config_test', ignore_errors=True)

    def testNoExistsDir(self):
        self.assertEqual(read_conf('_', self.config), self.config)

    def testExistsDir(self):
        self.assert_(read_conf('config_test', self.config))

    def testWriteConfig(self):
        test_config = read_conf('config_test', self.config)
        self.assertEqual(test_config['REPORT_SIZE'], 123)
        self.assertEqual(test_config['REPORT_DIR'], './reports_test')
        self.assertEqual(test_config['LOG_DIR'], './log_test')


class TestSearchLastLogFile(unittest.TestCase):
    def setUp(self):
        os.makedirs('test_log')
        for day in range(11, 17):
            f = open(os.path.join('test_log', f'nginx-access-ui.log-201506{day}'), 'w')
            f.close()

    def tearDown(self):
        shutil.rmtree('test_log', ignore_errors=True)

    def testSerchLastDateFile(self):
        Data_file = namedtuple('Data_file', 'file date')
        self.assertEqual(search_last_log_file('test_log', '^(nginx-access-ui.log-)(?P<date>\d{8})(\.gz)?$'),
                         (Data_file('nginx-access-ui.log-20150616', datetime.datetime.strptime('20150616', '%Y%m%d'))))

    def testNotDir(self):
        self.failIf(search_last_log_file('_', '_'))

    def testNotFile(self):
        print(search_last_log_file('test_log', '^(nginx)(\d{8})(\.gz)?$'))
        self.failIf(search_last_log_file('test_log', '_'))


class TestReadLog(unittest.TestCase):
    def setUp(self):
        os.makedirs('_test_file')
        data = """1.168.65.96 -  - [29/Jun/2017:03:50:23 +0300] "GET /api/v2/internal/banner/24288647/info HTTP/1.1" 200 351 "-" "-" "-" "1498697423-2539198130-4708-9752780" "89f7f1be37d" 0.072
1.169.137.128 -  - [29/Jun/2017:03:50:23 +0300] "POST /api/v2/banner/21456892 HTTP/1.1" 200 70795 "-" "Slotovod" "-" "1498697423-2118016444-4708-9752779" "712e90144abee9" 0.158
1.168.65.96 -  - [29/Jun/2017:03:50:23 +0300] "-" 200 293 "-" "-" "-" "1498697423-2539198130-4708-9752783" "89f7f1be37d" -"""
        f1 = open(os.path.join('_test_file', 'test.log'), 'w')
        f1.write(data)
        f1.close()
        f2 = gzip.open(os.path.join('_test_file', 'test.gz'), 'w')
        f2.write(data.encode(encoding='utf-8'))
        f2.close()

    def tearDown(self):
        shutil.rmtree('_test_file', ignore_errors=True)

    def testReadFile(self):
        data_lst = read_log(os.path.join('_test_file', 'test.log'), "\"(GET|POST|HEAD|PUT) (?P<url>\S+) \S+\".+ (?P<time>\d+\.\d+)\s{0,2}$")
        self.assertEqual(data_lst.__next__(), ('/api/v2/internal/banner/24288647/info', 0.072))
        self.assertEqual(data_lst.__next__(), ('/api/v2/banner/21456892', 0.158))
        self.assertEqual(data_lst.__next__(), None)


    def testReadGzip(self):
        data_lst = read_log(os.path.join('_test_file', 'test.gz'), "\"(GET|POST|HEAD|PUT) (?P<url>\S+) \S+\".+ (?P<time>\d+\.\d+)\s{0,2}$")
        self.assertEqual(data_lst.__next__(), ('/api/v2/internal/banner/24288647/info', 0.072))
        self.assertEqual(data_lst.__next__(), ('/api/v2/banner/21456892', 0.158))
        self.assertEqual(data_lst.__next__(), None)


class TestFormationReport(unittest.TestCase):
    def setUp(self):
        self.lst = [('url_1', 2), ('url_2', 6), ('url_1', 4), ('url_3', 12), ('url_2', 6)]

    def testGetReport(self):
        report = formation_report(self.lst, 2, 50)
        self.assertEqual(len(report), 2)
        print(report)
        self.assertEqual(report[0],
                         {'url': 'url_2',
                          'count': 2,
                          'count_perc': 40.0,
                          'time_sum': 12,
                          'time_perc': 40.0,
                          'time_avg': 6.0,
                          'time_max': 6,
                          'time_med': 6})
        self.assertEqual(report[1],
                         {'url': 'url_3',
                          'count': 1,
                          'count_perc': 20.0,
                          'time_sum': 12,
                          'time_perc': 40.0,
                          'time_avg': 12.0,
                          'time_max': 12,
                          'time_med': 12})


if __name__ == "__main__":
    unittest.main()
