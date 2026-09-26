import sys
sys.path.insert(0, "tools"); sys.path.insert(0, "app")
import pytest
import test_wave21_u as t
import streamlit as st
import pandas as pd
orig = st.data_editor
for values in ({"note": None}, {"origin": "measured ", "source": "условное значение для проверки BL-70 "}):
    def filled(frame, *a, **k):
        orig(frame, *a, **k)
        e = frame.copy()
        for c, v in {**t.ELASTIC_ROW_VALUES, **values}.items():
            e[c] = pd.Series([v]*len(e), index=e.index, dtype=object)
        return e
    st.data_editor = filled
    at = t._start(t.ELASTIC_NI20CR)
    at.button(key="b4b2_elastic_prepare_calculate").click().run()
    b = at.button(key="b4b2_elastic_vrh_calculate")
    print(values, "disabled:", b.proto.disabled)
    b.click().run()
    texts = [c.value for c in at.code] + [str(getattr(x, "value", "")) for x in at.get("json")]
    print([x for x in texts if "invalid" in x][:3])
    st.data_editor = orig
