# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import logging
import time

from courseware.models import XModuleUserStateSummaryField
from logging.handlers import TimedRotatingFileHandler


logger = logging.getLogger("edx.scripts.ilt_data_migrate")
log_handler = TimedRotatingFileHandler("/edx/var/log/lms/ilt_data_migrate.log",
                                       when="W0",
                                       backupCount=5,
                                       encoding="utf-8")
log_formatter = logging.Formatter('%(asctime)s [%(name)s] [%(filename)s:%(lineno)d] %(levelname)s  - %(message)s')
log_formatter.converter = time.gmtime
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)


def ilt_data_migrate():
    """
    tranform the old version ilt data to new version
    """
    summaries = XModuleUserStateSummaryField.objects.filter(field_name="sessions")
    for s in summaries:
        data = json.loads(s.value)
        query = XModuleUserStateSummaryField.objects.filter(usage_id=s.usage_id, field_name="enrolled_users")
        if query:
            user_data = query[0]
        else:
            user_data = None
        try:
            if 'counter' not in data:
                counter = 0
                tmp_sessions = {}
                tmp_enrolled_users = {}
                for k in data.keys():
                    counter += 1
                    tmp_sessions[counter] = data[k]
                    if user_data:
                        enrolled_users = json.loads(user_data.value)
                        if k in enrolled_users:
                            user_list = enrolled_users[k]
                            value = {str(n): {"status": "confirmed", "comment": "", "accommodation": "no",
                                              "number_of_return": 1, "number_of_one_way": 1} for n in user_list}
                            tmp_enrolled_users[counter] = value
                tmp_sessions['counter'] = counter
                s.value = json.dumps(tmp_sessions)
                s.save()
                if user_data:
                    user_data.value = json.dumps(tmp_enrolled_users)
                    user_data.save()

                logger.info("summary ID: {s_id}, usage_key: {key}, status: success".format(
                    s_id=s.id,
                    key=unicode(s.usage_id)
                ))
        except Exception as e:
            logger.error("summary ID: {s_id}, usage_key: {key}, status: failed, reason: {reason}".format(
                s_id=s.id,
                key=unicode(s.usage_id),
                reason=e
            ))


if __name__ == '__main__':
    logger.info("start ilt data migration...")
    ilt_data_migrate()
    logger.info("Done!")
