# knowledge_graph_ai

基于知识图谱的智能文书生成系统

## 项目简介

本项目是一个基于知识图谱的智能文档管理系统，能够自动提取、处理和存储企业产品资料，构建产品与文档之间的关联关系，并支持向量化检索和智能匹配。

## 主要功能

### 1. 数据提取与处理

#### Excel 产品信息提取
- **文件**: `src/extract_node_name_from_xlsx.py`
- **功能**: 使用 LLM（Qwen）自动分析 Excel 文件，提取产品及其配件列表
- **特点**:
  - 自动识别产品英文名、中文名、BOM版本和配件信息
  - 数据去重处理
  - 输出 JSON 格式的产品配件数据

#### 批量文件转换
- **文件**: `src/extract_file_from_raw_folder.py`
- **功能**: 批量转换多种格式文件
- **支持格式**:
  - PDF → Markdown（使用 mineru 库）
  - Excel (xlsx/xls) → Markdown
  - Word (docx) → JSON（包含文本、表格、图片的 base64 编码）
  - 图片 → PNG（统一格式转换）
- **特点**: 保持原文件夹目录结构

### 2. 知识图谱构建

#### Neo4j 数据导入
- **文件**: `src/neo4j_import_node_names.py`
- **功能**: 将产品和配件数据导入 Neo4j 图数据库
- **图结构**:
  - `Product` 节点：产品（标识符为 `product_english_name_bom_version`）
  - `Accessory` 节点：配件
  - `(Product)-[:HAS]->(Accessory)` 关系：产品包含配件

#### 文档与图片导入
- **文件**: `src/neo4j_file_add_neo4j.py`
- **功能**: 将处理后的文档和图片导入 Neo4j，建立完整的知识图谱
- **图结构**:
  - `Document` 节点：文档
  - `Image` 节点：图片
  - `TextDescription`、`ImageDescription`、`TableDescription` 节点：内容描述
  - `Chunk` 节点：文本块（带向量嵌入）
  - `Unknown` 节点：无法匹配的文档/图片
  - 关系：
    - `(Product/Accessory)-[:HAS_DOCUMENT]->(Document)`
    - `(Product/Accessory)-[:HAS_IMAGE]->(Image)`
    - `(Document)-[:HAS_TEXT_DESCRIPTION]->(TextDescription)`
    - `(Document)-[:HAS_IMAGE_DESCRIPTION]->(ImageDescription)`
    - `(Document)-[:HAS_TABLE_DESCRIPTION]->(TableDescription)`
    - `(Description)-[:HAS_CHUNK]->(Chunk)`

### 3. 智能匹配与分析

#### 文档智能匹配
- **功能**: 使用 LLM 自动分析文档内容，匹配到对应的产品或配件节点
- **流程**:
  1. 解析文档（Markdown/JSON），提取文本、图片、表格
  2. 使用 LLM 总结文本内容
  3. 使用视觉 LLM 分析图片内容
  4. 使用 LLM 总结表格内容
  5. 基于内容总结和节点列表，智能匹配到最相关的产品/配件

#### 内容向量化
- **功能**: 对文档内容进行分块和向量化
- **特点**:
  - 支持向量索引（Neo4j vector index）
  - 支持语义检索
  - 自动分块处理（基于 Markdown 结构）

### 4. 工具模块

- **`src/data_pdf.py`**: PDF 解析，使用 mineru 库转换为 Markdown
- **`src/data_excel.py`**: Excel 解析，转换为 Markdown 表格
- **`src/data_word.py`**: Word 文档解析，提取文本、表格、图片（base64）
- **`src/data_image.py`**: 图片格式转换工具
- **`src/neo4j_analysis.py`**: Neo4j 数据库分析工具
- **`src/models_litellm.py`**: LLM 模型配置（支持 Qwen、Ollama 等）
- **`src/dataclass.py`**: 数据类定义（LLMConfig、Neo4jConfig）

## 技术栈

- **图数据库**: Neo4j
- **LLM 框架**: LiteLLM（支持多种模型提供商）
- **文档处理**: 
  - mineru（PDF 解析）
  - python-docx（Word 解析）
  - pandas（Excel 处理）
- **向量化**: 支持多种 embedding 模型
- **图像处理**: PIL/Pillow

## 环境配置

### 必需环境变量

创建 `.env` 文件，配置以下变量：

```env
# Neo4j 配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=Root@12345678@

# LLM API 配置（根据使用的模型选择）
DASHSCOPE_API_KEY=your_api_key  # 用于 Qwen 模型
```

### 依赖安装

```bash
# 使用 uv 管理依赖（推荐）
uv pip install -r requirements.txt

# 或使用 pip
pip install -r requirements.txt
```

## 使用流程

### 1. 提取产品信息

```bash
# 从 Excel 提取产品配件信息
python src/extract_node_name_from_xlsx.py
```

### 2. 导入产品到 Neo4j

```bash
# 导入产品和配件节点
python src/neo4j_import_node_names.py
```

### 3. 批量转换文件

```bash
# 转换原始文件夹中的文件
python src/extract_file_from_raw_folder.py
```

### 4. 导入文档到知识图谱

```bash
# 批量导入文档和图片到 Neo4j
python src/neo4j_file_add_neo4j.py
```

## 项目结构

```
knowledge_graph_ai/
├── src/
│   ├── extract_node_name_from_xlsx.py    # Excel 产品信息提取
│   ├── neo4j_import_node_names.py         # 产品节点导入
│   ├── extract_file_from_raw_folder.py    # 批量文件转换
│   ├── neo4j_file_add_neo4j.py            # 文档导入知识图谱
│   ├── data_pdf.py                         # PDF 处理
│   ├── data_excel.py                       # Excel 处理
│   ├── data_word.py                        # Word 处理
│   ├── data_image.py                       # 图片处理
│   ├── neo4j_analysis.py                  # Neo4j 分析工具
│   ├── models_litellm.py                  # LLM 模型配置
│   └── dataclass.py                        # 数据类定义
├── README.md
└── .env                                    # 环境变量配置
```

