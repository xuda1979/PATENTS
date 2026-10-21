import sys
with open('/Users/daxu/software/quantum-gpt/scripts/huanxin_shell.sh', 'r') as f:
    content = f.read()

content = content.replace(
    '  ASI3) DEFAULT_PORT="19003" ;;',
    '  ASI3) DEFAULT_PORT="19003" ;;\n  ASI2) DEFAULT_PORT="19004" ;;'
)

content = content.replace(
    '  ASI3)\n    DEFAULT_TRAIN_DEV_URL="${TRAIN_DEV_BASE_URL}/environment/dl-c72bd81a96e33134bbe0ae4a478fbab0?name=ASI3"\n    ;;',
    '  ASI3)\n    DEFAULT_TRAIN_DEV_URL="${TRAIN_DEV_BASE_URL}/environment/dl-c72bd81a96e33134bbe0ae4a478fbab0?name=ASI3"\n    ;;\n  ASI2)\n    DEFAULT_TRAIN_DEV_URL="${TRAIN_DEV_BASE_URL}/detail/dl-868c196fb82d3e0b8cfbbe826d8afd0a"\n    ;;'
)

with open('/Users/daxu/software/quantum-gpt/scripts/huanxin_shell.sh', 'w') as f:
    f.write(content)
