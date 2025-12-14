{
    'name': '中国支付集成 - 支付宝与微信支付',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': '支付宝和微信支付集成模块，支持Odoo 17在线支付',
    'description': """
    支付宝与微信支付集成模块
    ======================
    
    本模块为Odoo 17提供支付宝和微信支付的完整集成解决方案：
    
    主要功能：
    - 支付宝电脑网站支付、手机网站支付、扫码支付
    - 微信支付JSAPI、Native扫码、H5支付
    - 完整的支付配置管理界面
    - 异步通知处理和订单状态同步
    - 退款功能和对账支持
    """,
    'author': 'Odoo开发专家',
    'website': 'https://www.odoo.com',
    'license': 'LGPL-3',
    'depends': [
        'payment',
        'website_sale',
        'account',
    ],
    'data': [
        'data/payment_provider_data.xml',
        'views/payment_provider_views.xml',
        'views/payment_templates.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
        'demo/payment_provider_demo.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'cn_payment_alipay_wechat/static/src/js/payment_form.js',
        ],
        'web.assets_backend': [
            'cn_payment_alipay_wechat/static/src/js/payment_provider.js',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'price': 0,
    'currency': 'EUR',
}