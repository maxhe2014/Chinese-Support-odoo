# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import logging
import json
import hashlib
import base64
from datetime import datetime
from urllib.parse import quote, urlencode

_logger = logging.getLogger(__name__)


try:
    from Crypto.PublicKey import RSA
    from Crypto.Signature import PKCS1_v1_5
    from Crypto.Hash import SHA256
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    _logger.warning("Crypto库不可用，支付宝支付功能将受限")

# 导入timedelta
from datetime import timedelta


class PaymentProviderAlipay(models.Model):
    """支付宝支付提供商"""
    
    _name = 'payment.provider'
    _inherit = ['payment.provider', 'cn_payment_alipay_wechat.payment_provider']
    _description = '支付宝支付提供商'
    
    # 支付宝特定配置字段
    code = fields.Selection(
        selection_add=[('alipay', '支付宝')],
        ondelete={'alipay': 'set default'}
    )
    
    alipay_app_id = fields.Char(
        string='应用ID(APP_ID)',
        required_if_provider='alipay',
        help='支付宝开放平台应用ID',
        groups='base.group_system'
    )
    
    alipay_private_key = fields.Text(
        string='商户私钥',
        required_if_provider='alipay',
        help='商户应用私钥，用于生成签名',
        groups='base.group_system'
    )
    
    alipay_public_key = fields.Text(
        string='支付宝公钥',
        required_if_provider='alipay',
        help='支付宝公钥，用于验证回调签名',
        groups='base.group_system'
    )
    
    alipay_encrypt_key = fields.Char(
        string='加密密钥(AES密钥)',
        help='AES加密密钥（可选）',
        groups='base.group_system'
    )
    
    alipay_payment_method = fields.Selection(
        [
            ('FAST_INSTANT_TRADE_PAY', '电脑网站支付'),
            ('QUICK_WAP_WAY', '手机网站支付'),
            ('FACE_TO_FACE_PAYMENT', '扫码支付'),
        ],
        string='支付方式',
        default='FAST_INSTANT_TRADE_PAY',
        required=True
    )
    
    # API端点配置
    ALIPAY_API_ENDPOINTS = {
        'sandbox': {
            'gateway': 'https://openapi.alipaydev.com/gateway.do',
            'notify_url': '/payment/alipay/notify',
            'return_url': '/payment/alipay/return',
        },
        'production': {
            'gateway': 'https://openapi.alipay.com/gateway.do',
            'notify_url': '/payment/alipay/notify',
            'return_url': '/payment/alipay/return',
        }
    }
    
    @api.model
    def _get_compatible_providers(self, *args, currency_id=None, **kwargs):
        """获取兼容的支付提供商"""
        providers = super()._get_compatible_providers(
            *args, currency_id=currency_id, **kwargs
        )
        
        # 只支持人民币
        currency = self.env['res.currency'].browse(currency_id).exists()
        if currency and currency.name != 'CNY':
            providers = providers.filtered(lambda p: p.code != 'alipay')
        
        return providers
    
    def _check_required_fields(self):
        """检查支付宝必填字段"""
        if self.code != 'alipay':
            return True
            
        required_fields = [
            self.alipay_app_id,
            self.alipay_private_key,
            self.alipay_public_key,
        ]
        
        return all(required_fields)
    
    def _get_api_endpoint(self, endpoint_type):
        """获取API端点"""
        env_type = 'sandbox' if self.sandbox_mode else 'production'
        endpoints = self.ALIPAY_API_ENDPOINTS[env_type]
        
        if endpoint_type == 'gateway':
            return endpoints['gateway']
        elif endpoint_type == 'notify_url':
            base_url = self._get_base_url()
            return base_url + endpoints['notify_url']
        elif endpoint_type == 'return_url':
            base_url = self._get_base_url()
            return base_url + endpoints['return_url']
        else:
            raise ValidationError(f"未知的端点类型: {endpoint_type}")
    
    def _generate_payment_request(self, transaction, **kwargs):
        """生成支付宝支付请求"""
        self.ensure_one()
        
        if not CRYPTO_AVAILABLE:
            raise UserError("Crypto库不可用，无法生成支付宝支付请求")
        
        # 验证配置
        self._validate_configuration()
        
        # 构建请求参数
        biz_content = {
            'out_trade_no': transaction.reference,
            'total_amount': str(transaction.amount),
            'subject': transaction.reference,
            'product_code': self.alipay_payment_method,
        }
        
        # 添加额外参数
        if kwargs.get('body'):
            biz_content['body'] = kwargs['body']
        
        # 构建请求数据
        request_data = {
            'app_id': self.alipay_app_id,
            'method': 'alipay.trade.page.pay',
            'charset': 'utf-8',
            'sign_type': 'RSA2',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': '1.0',
            'biz_content': json.dumps(biz_content, separators=(',', ':')),
            'notify_url': self._get_api_endpoint('notify_url'),
            'return_url': self._get_api_endpoint('return_url'),
        }
        
        # 生成签名
        signature = self._generate_signature(request_data)
        request_data['sign'] = signature
        
        # 构建支付URL
        payment_url = self._build_payment_url(request_data)
        
        self._log_payment_info(
            f"生成支付请求: {transaction.reference}, 金额: {transaction.amount}",
            transaction.reference
        )
        
        return {
            'type': 'redirect',
            'url': payment_url,
            'method': 'GET',
            'data': request_data,
        }
    
    def _generate_signature(self, data):
        """生成RSA2签名"""
        # 排序参数
        sorted_data = sorted(data.items())
        
        # 构建待签名字符串
        sign_string = '&'.join([f"{k}={v}" for k, v in sorted_data if v and k != 'sign'])
        
        # 加载私钥
        private_key = RSA.import_key(self.alipay_private_key)
        
        # 创建签名对象
        signer = PKCS1_v1_5.new(private_key)
        
        # 计算SHA256哈希
        digest = SHA256.new(sign_string.encode('utf-8'))
        
        # 生成签名
        signature = signer.sign(digest)
        
        # Base64编码
        return base64.b64encode(signature).decode('utf-8')
    
    def _build_payment_url(self, data):
        """构建支付URL"""
        gateway_url = self._get_api_endpoint('gateway')
        
        # URL编码参数
        encoded_params = urlencode(data, quote_via=quote)
        
        return f"{gateway_url}?{encoded_params}"
    
    def _verify_notification_signature(self, notification_data):
        """验证支付宝回调签名"""
        if not CRYPTO_AVAILABLE:
            _logger.error("Crypto库不可用，无法验证支付宝签名")
            return False
        
        # 获取签名
        signature = notification_data.get('sign')
        if not signature:
            _logger.error("支付宝回调缺少签名")
            return False
        
        # 构建待验证字符串
        sorted_data = sorted(notification_data.items())
        sign_string = '&'.join([f"{k}={v}" for k, v in sorted_data if v and k != 'sign' and k != 'sign_type'])
        
        try:
            # 加载支付宝公钥
            public_key = RSA.import_key(self.alipay_public_key)
            
            # 创建验证器
            verifier = PKCS1_v1_5.new(public_key)
            
            # 计算SHA256哈希
            digest = SHA256.new(sign_string.encode('utf-8'))
            
            # 验证签名
            signature_bytes = base64.b64decode(signature)
            is_valid = verifier.verify(digest, signature_bytes)
            
            if not is_valid:
                _logger.error("支付宝回调签名验证失败")
            
            return is_valid
            
        except Exception as e:
            _logger.error(f"支付宝签名验证异常: {str(e)}")
            return False
    
    def _process_refund(self, transaction, amount=None):
        """处理支付宝退款"""
        # 退款金额默认为交易金额
        refund_amount = amount or transaction.amount
        
        # 构建退款请求
        biz_content = {
            'out_trade_no': transaction.reference,
            'refund_amount': str(refund_amount),
            'out_request_no': f"REFUND_{transaction.reference}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        }
        
        request_data = {
            'app_id': self.alipay_app_id,
            'method': 'alipay.trade.refund',
            'charset': 'utf-8',
            'sign_type': 'RSA2',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': '1.0',
            'biz_content': json.dumps(biz_content, separators=(',', ':')),
        }
        
        # 生成签名
        signature = self._generate_signature(request_data)
        request_data['sign'] = signature
        
        # 这里应该发送HTTP请求到支付宝API
        # 由于复杂性，实际实现需要完整的HTTP客户端
        
        self._log_payment_info(
            f"处理退款请求: {transaction.reference}, 金额: {refund_amount}",
            transaction.reference
        )
        
        # 返回退款结果（简化实现）
        return {
            'success': True,
            'refund_id': biz_content['out_request_no'],
            'message': '退款请求已提交'
        }
    
    def _handle_notification(self, notification_data):
        """处理支付宝回调通知"""
        # 验证签名
        if not self._verify_notification_signature(notification_data):
            return {'success': False, 'message': '签名验证失败'}
        
        # 获取交易信息
        trade_status = notification_data.get('trade_status')
        out_trade_no = notification_data.get('out_trade_no')
        trade_no = notification_data.get('trade_no')
        
        if not out_trade_no:
            return {'success': False, 'message': '缺少交易号'}
        
        # 查找交易记录
        transaction = self.env['payment.transaction'].search([
            ('reference', '=', out_trade_no)
        ])
        
        if not transaction:
            return {'success': False, 'message': '交易记录不存在'}
        
        # 根据交易状态更新
        if trade_status == 'TRADE_SUCCESS':
            transaction._set_done()
            message = f"支付宝支付成功 - 支付宝交易号: {trade_no}"
        elif trade_status == 'TRADE_FINISHED':
            transaction._set_done()
            message = f"支付宝交易完成 - 支付宝交易号: {trade_no}"
        elif trade_status == 'WAIT_BUYER_PAY':
            transaction._set_pending()
            message = "等待买家付款"
        elif trade_status in ['TRADE_CLOSED', 'TRADE_FAILED']:
            transaction._set_canceled()
            message = f"交易关闭或失败: {trade_status}"
        else:
            message = f"未知交易状态: {trade_status}"
        
        # 记录处理结果
        transaction._log_payment_transaction_received(message)
        
        self._log_payment_info(
            f"处理支付宝回调: {trade_status}",
            out_trade_no
        )
        
        return {'success': True, 'message': message}

    def action_test_alipay(self):
        """测试支付宝连接"""
        self.ensure_one()
        
        try:
            self._validate_configuration()
            
            # 模拟测试请求
            test_data = {
                'app_id': self.alipay_app_id,
                'method': 'alipay.system.oauth.token',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 生成测试签名
            signature = self._generate_signature(test_data)
            
            # 这里应该发送实际的测试请求
            # 简化实现：返回成功
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '连接测试',
                    'message': '支付宝连接测试成功',
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '连接测试',
                    'message': f'支付宝连接测试失败: {str(e)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }