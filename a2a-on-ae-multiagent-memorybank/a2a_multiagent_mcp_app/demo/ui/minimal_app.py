import mesop as me
from mesop.cli import run

def on_load(e: me.LoadEvent):
    print("on_load event triggered in minimal_app")

@me.page(path="/", on_load=on_load)
def page():
    me.text("Hello, World!")

if __name__ == "__main__":
    run()

