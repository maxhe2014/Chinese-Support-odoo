# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class CNPaymentProvider(models.Model):
    """中国支付提供商基类"""
    
    _name = 'payment.provider'
    _inherit = ['payment.provider']
    _description = '中国支付提供商基类'
    
    # 通用配置字段
    sandbox_mode = fields.Boolean(
        string='沙箱模式',
        help='启用沙箱环境进行测试',
        default=True
    )
    
    # 货币支持
    @api.model
    def _get_supported_currencies(self):
        """获取支持的货币列表"""
        return ['CNY']
    
    def _get_validation_amounts(self):
        """获取验证金额"""
        return {
            'min_amount': 0.01,  # 最小金额（微信支付要求）
            'max_amount': 1000000.00,  # 最大金额
            'fixed_amount': 0.01,  # 固定验证金额
        }
    
    def _is_tokenization_required(self, **kwargs):
        """是否要求tokenization"""
        return False
    
    def _should_build_inline_form(self, **kwargs):
        """是否构建内联表单"""
        return False
    
    def _get_default_payment_method_id(self):
        """获取默认支付方法"""
        self.ensure_one()
        return self.env.ref('payment.payment_method_digital').id
    
    # 支付请求生成
    def _generate_payment_request(self, transaction, **kwargs):
        """生成支付请求 - 子类必须实现"""
        raise NotImplementedError("子类必须实现 _generate_payment_request 方法")
    
    # 通知验证
    def _verify_notification_signature(self, notification_data):
        """验证通知签名 - 子类必须实现"""
        raise NotImplementedError("子类必须实现 _verify_notification_signature 方法")
    
    # 退款处理
    def _process_refund(self, transaction, amount=None):
        """处理退款请求 - 子类必须实现"""
        raise NotImplementedError("子类必须实现 _process_refund 方法")
    
    # 工具方法
    def _get_base_url(self):
        """获取基础URL"""
        return self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    
    def _format_amount(self, amount, currency):
        """格式化金额"""
        if currency.name != 'CNY':
            raise ValidationError("只支持人民币(CNY)支付")
        
        # 微信支付要求金额以分为单位
        return int(amount * 100)
    
    def _log_payment_info(self, message, transaction_ref=None):
        """记录支付日志"""
        log_message = f"[{self.code}] {message}"
        if transaction_ref:
            log_message += f" - 交易号: {transaction_ref}"
        _logger.info(log_message)
    
    def _log_payment_error(self, message, transaction_ref=None):
        """记录支付错误"""
        log_message = f"[{self.code}] {message}"
        if transaction_ref:
            log_message += f" - 交易号: {transaction_ref}"
        _logger.error(log_message)
    
    # 安全验证
    def _validate_configuration(self):
        """验证配置完整性"""
        self.ensure_one()
        
        if not self._check_required_fields():
            raise ValidationError("支付配置不完整，请检查必填字段")
        
        return True
    
    def _check_required_fields(self):
        """检查必填字段 - 子类必须实现"""
        raise NotImplementedError("子类必须实现 _check_required_fields 方法")
    
    # API端点管理
    def _get_api_endpoint(self, endpoint_type):
        """获取API端点 - 子类必须实现"""
        raise NotImplementedError("子类必须实现 _get_api_endpoint 方法")