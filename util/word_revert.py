import spacy
import os

from api.basic_api import use_api_get_prototype
from log.log import Log
from util.runtime_paths import resource_path

# 模型目录：开发时是项目根目录；打包成 exe 后是解包目录
model_path = resource_path('en_core_web_sm')
module = Log("word_revert")

if not os.path.exists(model_path):
    module.logger.error(f"模型文件夹不存在: {model_path}")
elif not os.listdir(model_path):
    module.logger.error(f"模型文件夹为空: {model_path}")
else:
    module.logger.info(f"模型加载成功{model_path}")


def word_revert(word: str) -> str:
    """
    优先使用模型转原型
    :param word: 目标单词
    :return: 原型
    """
    try:
        nlp = spacy.load(model_path)
        module.logger.info(f"{word}优先使用模型转原型")
        doc = nlp(word)
        for token in doc:
            # 单词已是原型，直接返回
            if token.lemma_ == word:
                return word
            # 成功
            return token.lemma_
    except Exception as e:
        module.logger.error(f"模型加载失败")
        module.logger.error(e)
        return use_api_get_prototype(word)


if __name__ == '__main__':
    print(word_revert('done'))