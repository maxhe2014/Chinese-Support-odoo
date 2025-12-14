# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging
import json

_logger = logging.getLogger(__name__)


class CNPaymentController(http.Controller):
    """中国支付控制器"""
    
    @http.route('/payment/alipay/notify', type='http', auth='public', methods=['POST'], csrf=False)
    def alipay_notify(self, **post):
        """支付宝异步通知处理"""
        _logger.info("收到支付宝回调通知: %s", post)
        
        try:
            # 查找支付宝支付提供商
            provider = request.env['payment.provider'].search([
                ('code', '=', 'alipay'),
                ('state', '=', 'enabled')
            ], limit=1)
            
            if not provider:
                _logger.error("未找到启用的支付宝支付提供商")
                return "failure"
            
            # 处理通知
            result = provider._handle_notification(post)
            
            if result.get('success'):
                _logger.info("支付宝回调处理成功: %s", result.get('message'))
                return "success"
            else:
                _logger.error("支付宝回调处理失败: %s", result.get('message'))
                return "failure"
                
        except Exception as e:
            _logger.error("支付宝回调处理异常: %s", str(e))
            return "failure"
    
    @http.route('/payment/alipay/return', type='http', auth='public', methods=['GET'])
    def alipay_return(self, **get):
        """支付宝同步返回处理"""
        _logger.info("支付宝同步返回: %s", get)
        
        try:
            # 获取交易号
            out_trade_no = get.get('out_trade_no')
            if not out_trade_no:
                _logger.error("支付宝返回缺少交易号")
                return request.redirect('/shop/payment')
            
            # 查找交易记录
            transaction = request.env['payment.transaction'].search([
                ('reference', '=', out_trade_no)
            ], limit=1)
            
            if not transaction:
                _logger.error("未找到交易记录: %s", out_trade_no)
                return request.redirect('/shop/payment')
            
            # 根据交易状态重定向
            if transaction.state == 'done':
                # 支付成功，重定向到确认页面
                return request.redirect('/shop/confirmation')
            else:
                # 支付失败或待处理，重定向到支付页面
                return request.redirect(f'/shop/payment?error={transaction.state}')
                
        except Exception as e:
            _logger.error("支付宝返回处理异常: %s", str(e))
            return request.redirect('/shop/payment')
    
    @http.route('/payment/wechatpay/notify', type='http', auth='public', methods=['POST'], csrf=False)
    def wechatpay_notify(self, **post):
        """微信支付异步通知处理"""
        _logger.info("收到微信支付回调通知")
        
        try:
            # 获取原始请求数据
            raw_data = request.httprequest.get_data().decode('utf-8')
            headers = dict(request.httprequest.headers)
            
            # 构建通知数据
            notification_data = {
                'body': raw_data,
                'Wechatpay-Signature': headers.get('Wechatpay-Signature'),
                'Wechatpay-Timestamp': headers.get('Wechatpay-Timestamp'),
                'Wechatpay-Nonce': headers.get('Wechatpay-Nonce'),
                'Wechatpay-Serial': headers.get('Wechatpay-Serial'),
            }
            
            # 查找微信支付提供商
            provider = request.env['payment.provider'].search([
                ('code', '=', 'wechatpay'),
                ('state', '=', 'enabled')
            ], limit=1)
            
            if not provider:
                _logger.error("未找到启用的微信支付提供商")
                return json.dumps({'code': 'FAIL', 'message': '支付提供商未找到'})
            
            # 处理通知
            result = provider._handle_notification(notification_data)
            
            if result.get('success'):
                _logger.info("微信支付回调处理成功: %s", result.get('message'))
                return json.dumps({'code': 'SUCCESS', 'message': 'OK'})
            else:
                _logger.error("微信支付回调处理失败: %s", result.get('message'))
                return json.dumps({'code': 'FAIL', 'message': result.get('message')})
                
        except Exception as e:
            _logger.error("微信支付回调处理异常: %s", str(e))
            return json.dumps({'code': 'FAIL', 'message': str(e)})
    
    @http.route('/payment/wechatpay/return', type='http', auth='public', methods=['GET'])
    def wechatpay_return(self, **get):
        """微信支付同步返回处理"""
        _logger.info("微信支付同步返回: %s", get)
        
        try:
            # 微信支付通常没有同步返回，这里处理可能的错误情况
            error_code = get.get('error_code')
            error_msg = get.get('error_msg')
            
            if error_code:
                _logger.warning("微信支付返回错误: %s - %s", error_code, error_msg)
                return request.redirect(f'/shop/payment?error={error_code}')
            
            # 默认重定向到支付页面
            return request.redirect('/shop/payment')
            
        except Exception as e:
            _logger.error("微信支付返回处理异常: %s", str(e))
            return request.redirect('/shop/payment')
    
    @http.route('/payment/qrcode/<string:transaction_ref>', type='http', auth='public')
    def generate_qrcode(self, transaction_ref, **kwargs):
        """生成支付二维码"""
        _logger.info("生成支付二维码: %s", transaction_ref)
        
        try:
            # 查找交易记录
            transaction = request.env['payment.transaction'].search([
                ('reference', '=', transaction_ref)
            ], limit=1)
            
            if not transaction:
                _logger.error("未找到交易记录: %s", transaction_ref)
                return request.not_found()
            
            # 获取支付提供商
            provider = transaction.provider_id
            
            if provider.code == 'wechatpay':
                # 微信支付二维码
                # 这里应该生成真正的二维码图片
                # 简化实现：返回二维码数据URL
                qr_data = {
                    'type': 'wechatpay',
                    'transaction_ref': transaction_ref,
                    'amount': transaction.amount,
                    'status': transaction.state
                }
                
                return request.render('cn_payment_alipay_wechat.wechatpay_qrcode', {
                    'qr_data': qr_data,
                    'transaction': transaction
                })
            
            elif provider.code == 'alipay':
                # 支付宝二维码
                qr_data = {
                    'type': 'alipay',
                    'transaction_ref': transaction_ref,
                    'amount': transaction.amount,
                    'status': transaction.state
                }
                
                return request.render('cn_payment_alipay_wechat.alipay_qrcode', {
                    'qr_data': qr_data,
                    'transaction': transaction
                })
            
            else:
                _logger.error("不支持的支付提供商: %s", provider.code)
                return request.not_found()
                
        except Exception as e:
            _logger.error("生成二维码异常: %s", str(e))
            return request.not_found()
    
    @http.route('/payment/status/<string:transaction_ref>', type='json', auth='public')
    def check_payment_status(self, transaction_ref, **kwargs):
        """检查支付状态（AJAX接口）"""
        _logger.info("检查支付状态: %s", transaction_ref)
        
        try:
            # 查找交易记录
            transaction = request.env['payment.transaction'].search([
                ('reference', '=', transaction_ref)
            ], limit=1)
            
            if not transaction:
                return {'success': False, 'message': '交易记录不存在'}
            
            return {
                'success': True,
                'state': transaction.state,
                'amount': transaction.amount,
                'currency': transaction.currency_id.name,
                'reference': transaction.reference
            }
            
        except Exception as e:
            _logger.error("检查支付状态异常: %s", str(e))
            return {'success': False, 'message': str(e)}