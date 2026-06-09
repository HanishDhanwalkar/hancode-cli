# TODO: AVAILABLE_MODELS in .env - append ollama models using ollama.list_models() and filter by some criteria (e.g. only 8b models, or models with "deepseek" in the name, etc.)

## BUGs

[] -
    ```shell
    hancode: /memory
    Traceback (most recent call last):
    File "<frozen runpy>", line 198, in _run_module_as_main
    File "<frozen runpy>", line 88, in _run_code
    File "C:\Users\Hanish\Desktop\New-Researches\hancode-cli\src\__main__.py", line 4, in <module>
        main()
        ~~~~^^
    File "C:\Users\Hanish\Desktop\New-Researches\hancode-cli\src\cli.py", line 334, in main
        result = handle_slash(cmd, args, agent)
    File "C:\Users\Hanish\Desktop\New-Researches\hancode-cli\src\cli.py", line 205, in handle_slash
        return agent.project_memory or "(empty — edit .hancode/MEMORY.md)"
            ^^^^^^^^^^^^^^^^^^^^
    AttributeError: 'AgentOrchestrator' object has no attribute 'project_memory'
    ```

[] -
    ```shell
    hancode: /plan <something something>
    Traceback (most recent call last):
    File "<frozen runpy>", line 198, in _run_module_as_main
    File "<frozen runpy>", line 88, in _run_code
    File "C:\Users\Hanish\Desktop\New-Researches\hancode-cli\src\__main__.py", line 4, in <module>
        main()
        ~~~~^^
    File "C:\Users\Hanish\Desktop\New-Researches\hancode-cli\src\cli.py", line 334, in main
        result = handle_slash(cmd, args, agent)
    File "C:\Users\Hanish\Desktop\New-Researches\hancode-cli\src\cli.py", line 144, in handle_slash
        plan = agent.create_plan(args.strip())
            ^^^^^^^^^^^^^^^^^
    AttributeError: 'AgentOrchestrator' object has no attribute 'create_plan'
    ```