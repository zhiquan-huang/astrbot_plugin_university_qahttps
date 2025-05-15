from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import AstrBotConfig
from astrbot.api import logger
import json
import os
from pathlib import Path
from thefuzz import process

PLUGIN_DIR = Path(__file__).parent
questions_DATA_PATH = PLUGIN_DIR / "questions.json"


@register("高考咨询_qa", "阿咪", "高考咨询插件", "1.0.0")
class SZTUQAPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config  # 自动加载配置
        self.questions_data = self._load_data(questions_DATA_PATH, default={})

    
    def _check_whitelist(self, event: AstrMessageEvent) -> bool:
        group_id = event.get_group_id()
        return group_id in self.config["whitelist"]

    def _load_data(self, path: str, default=None):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return default
        except json.JSONDecodeError:
            print(f"JSON 文件 {path} 解码错误，已返回默认值。")
            return default
        except Exception as e:
            print(f"加载数据文件 {path} 失败: {traceback.format_exc()}")
            return default

    @filter.command_group("咨询群聊配置")
    @filter.permission_type(filter.PermissionType.ADMIN)  # 仅管理员可操作
    def whitelist_group(self):
        """白名单管理指令组"""
        pass

    @whitelist_group.command("新增")
    async def whitelist_add(self, event: AstrMessageEvent, group_id: str):
        '''添加群到白名单，用法：/whitelist add 群号'''
        if not group_id.isdigit():
            yield event.plain_result("❌ 群号必须为纯数字，例如：12345678")
            return
        
        if group_id in self.config["whitelist"]:
            yield event.plain_result(f"⚠️ 群 {group_id} 已在白名单中")
        else:
            self.config["whitelist"].append(group_id)
            self.config.save_config()
            yield event.plain_result(f"✅ 已添加群 {group_id} 到白名单")

    @whitelist_group.command("删除")
    async def whitelist_remove(self, event: AstrMessageEvent, group_id: str):
        '''从白名单移除群，用法：/whitelist remove 群号'''
        if not group_id.isdigit():
            yield event.plain_result("❌ 群号必须为纯数字，例如：12345678")
            return
        
        if group_id not in self.config["whitelist"]:
            yield event.plain_result(f"⚠️ 群 {group_id} 不在白名单中")
        else:
            self.config["whitelist"].remove(group_id)
            self.config.save_config()
            yield event.plain_result(f"✅ 已从白名单移除群 {group_id}")

    # ---------- 可选：查看白名单 ----------
    @whitelist_group.command("list")
    async def whitelist_list(self, event: AstrMessageEvent):
        '''查看当前白名单，用法：/whitelist list'''
        if not self.config["whitelist"]:
            yield event.plain_result("当前白名单为空")
        else:
            yield event.plain_result("白名单群号列表：\n" + "\n".join(self.config["whitelist"]))

    @filter.command("提问")
    async def handle_question(self, event: AstrMessageEvent, question: str):
        '''仅限白名单群聊响应'''
        if not self._check_whitelist(event):
            logger.info(f"群 {event.get_group_id()} 不在白名单，已拒绝请求")
            return  # 直接退出，不发送任何响应
        
        '''模糊匹配问题'''
        if not question.strip():
            yield event.plain_result("请输入问题关键词，例如：/提问 学校简介")
            return

        # 模糊匹配最接近的问题
        # 从问答数据库中提取所有问题关键词
        all_questions = list(self.qa_data.keys())
        
        # 使用模糊匹配找到最接近的问题（阈值设为70%）
        matched_question, similarity_score = process.extractOne(
            question, 
            all_questions, 
            score_cutoff=70
        )
        
        if matched_question:
            answer = self.qa_data[matched_question]
            # 处理图片类型回答
            if isinstance(answer, dict) and "image" in answer:
                image_path = answer["image"]
                if os.path.exists(image_path):
                    chain = [
                        Comp.Plain(f"您可能想问：'{matched_question}'\n{answer['text']}"),
                        Comp.Image.fromFileSystem(image_path)
                    ]
                    yield event.chain_result(chain)
                else:
                    logger.error(f"图片文件不存在: {image_path}")
                    yield event.plain_result("图片资源加载失败，请联系管理员。")
            else:
                yield event.plain_result(f"您可能想问：'{matched_question}'\n{answer}")
        else:
            yield event.plain_result("未找到相关回答，请尝试其他关键词，或咨询其他学长。若要求补充回答可联系开发者阿咪。可以尝试以下关键词：\n" + "\n".join(all_questions[:3]))