import dearpygui
print(dearpygui.__version__)

import dearpygui.dearpygui as dpg

dpg.create_context()
dpg.create_viewport(title="Test Dear PyGui", width=600, height=400)
dpg.setup_dearpygui()

with dpg.window(label="Test Window"):
    dpg.add_text("If you see this, Dear PyGui works!")
    dpg.add_button(label="Close", callback=lambda: dpg.stop_dearpygui())

dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
