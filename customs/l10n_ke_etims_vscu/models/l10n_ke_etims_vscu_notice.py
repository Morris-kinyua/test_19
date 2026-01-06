# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models, api

_logger = logging.getLogger(__name__)


class L10nKeVSCUNotice(models.Model):
    _name = 'l10n_ke_etims_vscu.notice'
    _description = "eTIMS Notices"

    number = fields.Integer()
    title = fields.Char()
    contents = fields.Char()
    detail_url = fields.Char()

    @api.model
    def _cron_l10n_ke_oscu_get_notices(self):
        """ Fetch and create notices issued by the KRA """
        company = self.env.company

        # The API will return all codes added since this date
        last_request_date = self.env['ir.config_parameter'].get_param('l10n_ke_vscu.last_notice_request_date', '20180101000000')
        error, data, _date = company._l10n_ke_call_etims('notices/selectNotices', {'lastReqDt': last_request_date})
        if error:
            if error['code'] == '001':
                _logger.info("No new KRA notices fetched from eTIMS.")
                return
            _logger.error("eTIMS Request Error [%s]: %s", error['code'], error['message'])

        notice_map = {notice['noticeNo']: notice for notice in data['noticeList']}
        pre_existing_notices = self.search([('number', 'in', list(notice_map.keys()))])
        self.create([{
            'number':     notice_number,
            'title':      notice['title'],
            'contents':   notice['cont'],
            'detail_url': notice['dtlUrl'],
        } for notice_number, notice in notice_map.items() if notice_number not in pre_existing_notices.mapped('number')])

        for notice in pre_existing_notices:
            notice_data = notice_map[notice.number]
            notice.write({
                'title': notice_data['title'],
                'contents': notice_data['cont'],
                'detail_url': notice_data['dtlUrl'],
            })
        _logger.info("%i KRA notices fetched from eTIMS", len(notice_map))
