"""
分类体系定义
预定义的分类树结构，LLM 从中选择最合适的类别
"""

# 预定义的分类体系
CATEGORY_TAXONOMY = {
    "产品资料": {
        "description": "产品相关的图片、文档、规格等资料",
        "subcategories": {
            "产品图片": "产品外观、细节、场景图片",
            "规格页": "产品规格说明、参数表",
            "产品手册": "产品使用手册、说明书",
            "技术文档": "技术规格、工程图纸",
            "产品目录": "产品目录、产品列表"
        }
    },
    "营销素材": {
        "description": "用于营销推广的素材",
        "subcategories": {
            "展会宣传": "展会海报、展位设计、展会照片",
            "社媒素材": "社交媒体图片、文案、视频",
            "海报设计": "宣传海报、广告设计",
            "视频素材": "宣传视频、产品视频",
            "品牌素材": "Logo、品牌指南、VI设计"
        }
    },
    "生产采购": {
        "description": "生产和采购相关的文档",
        "subcategories": {
            "BOM表": "物料清单、配件清单",
            "入库表": "入库单、库存表",
            "采购单": "采购订单、采购合同",
            "供应商资料": "供应商信息、联系方式",
            "生产计划": "生产排期、生产报表"
        }
    },
    "安装售后": {
        "description": "安装和售后服务相关的文档",
        "subcategories": {
            "安装说明": "安装指南、安装步骤",
            "用户手册": "用户使用手册、操作指南",
            "故障排查": "故障诊断、维修指南",
            "维护指南": "保养说明、维护手册",
            "售后服务": "售后政策、保修说明"
        }
    },
    "证书合规": {
        "description": "证书、检测报告、合规文档",
        "subcategories": {
            "产品证书": "认证证书、资质证书",
            "检测报告": "质检报告、测试报告",
            "合规文档": "合规声明、符合性文件",
            "专利文件": "专利证书、知识产权文件",
            "标准文档": "行业标准、技术标准"
        }
    },
    "内部管理": {
        "description": "公司内部管理文档",
        "subcategories": {
            "会议记录": "会议纪要、决议",
            "培训资料": "培训课件、培训视频",
            "流程文档": "工作流程、操作规范",
            "报表统计": "数据报表、统计分析",
            "其他文档": "其他内部文档"
        }
    }
}


def get_all_categories():
    """获取所有类别的列表"""
    categories = []
    for l1, data in CATEGORY_TAXONOMY.items():
        for l2, desc in data["subcategories"].items():
            categories.append({
                "l1": l1,
                "l2": l2,
                "l1_desc": data["description"],
                "l2_desc": desc,
                "full_path": f"{l1}/{l2}"
            })
    return categories


def get_category_prompt():
    """生成用于 LLM 的分类提示"""
    lines = ["可选的分类体系：\n"]
    for l1, data in CATEGORY_TAXONOMY.items():
        lines.append(f"\n{l1}（{data['description']}）：")
        for l2, desc in data["subcategories"].items():
            lines.append(f"  - {l2}：{desc}")
    return "\n".join(lines)


def validate_category(l1: str, l2: str) -> bool:
    """验证类别是否存在于预定义体系中"""
    if l1 not in CATEGORY_TAXONOMY:
        return False
    if l2 not in CATEGORY_TAXONOMY[l1]["subcategories"]:
        return False
    return True


def get_closest_category(l1: str, l2: str):
    """
    如果 LLM 返回的类别不在预定义体系中，找到最接近的类别
    """
    # 简单的模糊匹配
    all_cats = get_all_categories()
    
    # 精确匹配
    for cat in all_cats:
        if cat["l1"] == l1 and cat["l2"] == l2:
            return cat["l1"], cat["l2"]
    
    # L1 匹配
    for cat in all_cats:
        if cat["l1"] == l1:
            return cat["l1"], cat["l2"]
    
    # 关键词匹配
    for cat in all_cats:
        if l1 in cat["l1"] or cat["l1"] in l1:
            if l2 in cat["l2"] or cat["l2"] in l2:
                return cat["l1"], cat["l2"]
    
    # 默认返回第一个类别
    return all_cats[0]["l1"], all_cats[0]["l2"]


if __name__ == "__main__":
    # 测试
    print(get_category_prompt())
    print("\n" + "=" * 60)
    print(f"总共 {len(get_all_categories())} 个类别")
