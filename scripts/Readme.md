# 生成大区模式业务域
python scripts/generate_test_md.py --domain demo-region --profile region --clean

# 生成硬上限模式业务域
python scripts/generate_test_md.py --domain demo-core --profile core --clean

# 清理所有旧业务域并生成
python scripts/generate_test_md.py --domain demo-region --profile region --clean --clean-all

# 打包

python .\scripts\pack-project.py