#- coding:utf-8 -*-

"""
    1. 分析 go mod graph 的输出，整理模块之间的依赖关系
    2. 对模块去重
    3. 获取 模块在 github 上的说明
    4. 显示 模块的依赖关系报告，并附带上说明（表格形式）
    5. 模块上增加书签

    依赖：
    - pip install PyGithub
"""
import sys
import os
import json
import base64


def get_modulename_base(module_name:str) -> str:
    at_pos = module_name.find('@')
    if at_pos != -1:
        return module_name[:at_pos]
    return module_name

def load_go_mod_graph(fh):
    modules = dict()
    
    def add_dependency(mod_in, mod_out):
        if mod_in in modules:
            # 不去重
            modules[mod_in]['deps'].append(mod_out)
        else:
            modules[mod_in] = {
                'deps': [mod_out, ],
                'git_repo_info': 'nil'  # 不使用 ''， 便于判断
            }

        if mod_out not in modules:
            modules[mod_out] = {
                'deps': [ ],
                'git_repo_info': 'nil'  # 不使用 ''， 便于判断
            }
    
    root_module = None
    for line in fh:
        mod_in, mod_out = line.strip().split(' ')
        add_dependency(get_modulename_base(mod_in), get_modulename_base(mod_out))
        if not root_module:
            root_module = mod_in

    return root_module, modules

def get_repo_info(access_token, repo_list):
    from github import Github, UnknownObjectException
    g = Github(access_token)

    repo_info = dict()

    for repo in repo_list:
        if repo[:11] == 'github.com/':
            # addtional process for eg.  coreos/go-systemd/v22
            repo_short = repo[11:].split('/')
            info = g.get_repo('/'.join(repo_short[:2]))
            try:
                info_readme = info.get_readme()
                """
                if info_readme.encoding == 'base64':
                    info_readme = base64.b64decode(info.get_readme().content)
                print(info_readme, info.description)
                """
                repo_info[repo] = {
                    'readme_encoding': info_readme.encoding,
                    'readme_content':  info_readme.content,
                    'description': info.description
                }
            except UnknownObjectException:
                repo_info[repo] = {
                    'readme_encoding': 'text',
                    'readme_content':  '',
                    'description': info.description
                }
                pass

    # ()
    return repo_info


def render_output(root_module, repo_dag, repo_info, output_fname):
    from jinja2 import Template
    template = Template("""<html><head>
        <title>xxxx</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/showdown/1.9.1/showdown.min.js" ></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.4.1/jquery.min.js" ></script>
        <style>
            /* Popup box BEGIN */
            .hover_bkgr_fricc{
                background:rgba(0,0,0,.4);
                cursor:pointer;
                display:none;
                height:100%;
                position:fixed;
                top:0;
                width:100%;
                z-index:10000;
            }
            .hover_bkgr_fricc .helper{
                display:inline-block;
                height:100%;
                vertical-align:middle;
            }
            .hover_bkgr_fricc > div {
                background-color: #fff;
                box-shadow: 10px 10px 60px #555;
                display: inline-block;
                max-height: 800px;
                overflow:scroll; 
                max-width: 95%;
                min-height: 100px;
                vertical-align: top;
                width: 80%;
                position: relative;
                border-radius: 8px;
                padding: 15px 5%;
            }
            .popupCloseButton {
                background-color: #fff;
                border: 3px solid #999;
                border-radius: 50px;
                cursor: pointer;
                display: inline-block;
                font-family: arial;
                font-weight: bold;
                position: absolute;
                top: -20px;
                right: -20px;
                font-size: 25px;
                line-height: 30px;
                width: 30px;
                height: 30px;
                text-align: center;
            }
            .popupCloseButton:hover {
                background-color: #ccc;
            }
            .trigger_popup_fricc {
                cursor: pointer;
                display: inline-block;
                font-weight: bold;
            }
            /* Popup box BEGIN */
        </style>
    </head>
    <body>
<div class="hover_bkgr_fricc">
    <span class="helper"></span>
    <div id="hover_ctx">
        <div class="popupCloseButton">&times;</div>
        <p>&nbsp;</p>
    </div>
</div>

    {% for m in modules %}
    <h2 id="{{ m|e }}">{{ m|e }}</h2>
    <hr>
    <table>
        <tr>
            <th> repo </th>
            <th> package </th>
            <th> description </th>
        </tr>
        {% for sub_m in repo_dependency.get(m, {'deps':[]})['deps'] %}
        <tr>
            <td nowrap> <a href="http://{{ sub_m | e }}">repo</a> &nbsp;&nbsp; <a href="#{{ sub_m | e }}">#</a> &nbsp;&nbsp;
                 
            </td>
                   
            {% with sub_m_info=repo_info.get(sub_m, {'description':'', 'readme_encoding': 'text', 'readme_content':  '' }) %}
            <td nowrap> <a href="#{{ m|e }}" class="trigger_popup_fricc" data-enc="{{ sub_m_info['readme_encoding'] }}" data-readme="{{ sub_m_info['readme_content'] }}" > {{ sub_m | e }} </a> </td>
            <td> {{  sub_m_info['description'] | e }} </td>
            {% endwith %}
        </tr>
        {% endfor %}
    </table>
    {% endfor %}

    <script>
    $(window).on('load', function () {
        $(".trigger_popup_fricc").click(function(){
            if ($(this).attr("data-enc") == "base64") {
                ctx = window.atob($(this).attr("data-readme"));
                var converter = new showdown.Converter();
                text      = ctx;
                html      = converter.makeHtml(text);
                $('#hover_ctx').html(html);
            }
            $('.hover_bkgr_fricc').show();
        });
        $('.hover_bkgr_fricc').click(function(){
            $('.hover_bkgr_fricc').hide();
        });
        $('.popupCloseButton').click(function(){
            $('.hover_bkgr_fricc').hide();
        });
    });
    </script>
    </body>
    </html>""")

    # 调整 模块顺序为 宽度优先遍历
    modules = list()
    modules.append(root_module)

    def add_dependency(parent_module , repo_dag, modules_list):
        """
            实际上，生成的模块依赖关系存在 环，需要额外的检测。并不是 DAG.
        """
        """
        # ugly debug
        if len(modules_list) > 10000:
            exit(0)
            return modules_list
        """
        rs = []
        # print('deps', parent_module, (modules_list))

        for m in repo_dag[parent_module]['deps']:
            if m not in modules_list and m not in rs:
                rs.append(m)

        new_deps = rs.copy()
        for m in rs:
            new_deps += add_dependency(m, repo_dag, modules_list + new_deps)
            pass

        return new_deps

    modules += add_dependency(root_module, repo_dag, [])

    ctx = template.render(modules=modules, repo_dependency= repo_dag, repo_info= repo_info)
    with open(output_fname, 'w') as fh:
        fh.write(ctx)


if __name__ == '__main__':
    fname = sys.argv[1]

    db_fname = fname+'.json'
    repo_info_fname = fname + '_repo.json'

    if not os.path.exists(db_fname) or True:
        # try create dependency db
        with open(fname, 'r') as fh:
            root_module, modules = load_go_mod_graph(fh)
            
        with open(db_fname, 'w') as fh:
            json.dump(modules, fh)

    # json file  must exist
    with open(db_fname, 'r') as fh:
        modules = json.load(fh)

    # ensure deps uniq
    for k, v in modules.items():
        modules[k]['deps'] = list(set(v['deps']))

    access_token = os.environ['GITHUB_TOKEN']
    repo_list = list(modules.keys())

    repos_infos = dict()
    if os.path.exists(repo_info_fname):
        with open(repo_info_fname, 'r') as fh:
            repos_infos = json.load(fh)

    for i in range(0, len(repo_list), 10):
        repos = repo_list[i:i+10]
        new_repo = []
        for repo in repos:
            # print(repo, repos_infos.keys())
            if repos_infos.get(repo, None) is None:
                new_repo.append(repo)

        if new_repo:
            print("fetch", new_repo)
            # fetch info
            batch_repo_infos = get_repo_info(access_token, new_repo)

            if batch_repo_infos:
                repos_infos.update(batch_repo_infos)

                with open(repo_info_fname, 'w') as fh:
                    json.dump(repos_infos, fh)

    # 处理输出
    render_output(root_module, modules, repos_infos, 'modules.html')
