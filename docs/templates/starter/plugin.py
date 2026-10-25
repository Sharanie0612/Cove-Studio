from toolbench.sdk import Plugin


class Tool(Plugin):
    def greet(self, name="开发者"):
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise ValueError(self.context.t("姓名需要 1–80 个字符"))
        return {"message": self.context.t("你好，{name}！", name=name.strip())}
