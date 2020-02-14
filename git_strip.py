#- coding:utf-8 -*-

"""
用于迁移其他项目的 Git 仓库

- 其他项目的仓库可能混合多种不同的代码功能，如果只使用一部分代码，从其中 fork 在开发，原来历史中的代码回一直遗留在项目中。

此工具用于，

1. 遍历历史项目的变更记录，只保留影响到指定目录的变更
2. 使用原来的提交信息重新提交，并记录原来仓库对应的 hash 
3. 对于在第一个提交出现时，已经存在的文件，则进行删除
    - 对于移动文件的操作，需要额外进行特殊处理
    - 对于原始库的移动，可处理为新增
    - 对于原始库的移动，可迁移文件的变更，因此需要对文件进行染色

使用 pygit2, 

> pip install pygit2

https://github.com/libgit2/pygit2

"""

"""
处理流程：

1. 从最新的 commit 开始，遍历前面的 commit ，找到相关的 commit
2. 检测目标目录外的文件，追踪涉及的移动出的文件。
"""

import os
import sys
import json
import io

from pygit2 import Repository
from pygit2 import GIT_SORT_TOPOLOGICAL, GIT_SORT_REVERSE


def has_related_file(fname, path_list):
    related = False
    for p in path_list:
        if fname.startswith(p):
            related = True
    return related


def mark_comments(repo_name, path_list=[], max_depth=0):
    """
        标记影响 path_list 中文件的 commit, 返回  id 列表
    """

    def outside_move_in(new_fname, old_fname, path_list):
        """
            在目标项目中,没有出现类似情况,暂不处理(额外的文件标记 作色问题).
        """
        if has_related_file(new_fname, path_list) and not has_related_file(old_fname, path_list):
            print(old_fname, '->', new_fname)
        pass

    repo_realpath = os.path.join(repo_name, '.git')
    
    repo = Repository(repo_realpath)

    rs_comments = list()
    depth = 0
    prev_tree = None
    for commit in repo.walk(repo.head.target, GIT_SORT_TOPOLOGICAL):
        if prev_tree:
            changes = prev_tree.diff_to_tree(commit.tree)
            for c in changes:
                c_delta = c.delta
                # 与源文件相关 或 与修改过的文件相关
                if has_related_file(c_delta.new_file.path, path_list) \
                    or has_related_file(c_delta.old_file.path, path_list):
                    rs_comments.append(str(commit.oid))
                    # 检测有没有移动到本地目录的
                    outside_move_in(c_delta.new_file.path, c_delta.old_file.path, path_list)

        if max_depth and depth == max_depth:
            return rs_comments
        depth += 1
        prev_tree = commit.tree
    
    return rs_comments

def export_patches(repo_name, comments, target_path, path_list=[]):
    """
        从 repo 中读取相关的 comments , 并应用到 target_path 中, 默认为 .target
            - comments 已经按提交的顺序 排好
    """
    repo_realpath = os.path.join(repo_name, '.git')
    
    repo = Repository(repo_realpath)
    
    ht_comments =dict(zip(comments, comments))

    cnt = 0
    prev_tree = None
    prev_k = None

    for commit in repo.walk(repo.head.target, GIT_SORT_TOPOLOGICAL|GIT_SORT_REVERSE):
        k = str(commit.oid)
        if prev_k and prev_k in ht_comments:
            """
                临时方案 
                1: 将 diff 输出到以 commits 命名的临时文件夹
                2. 应用 patch, 重新提交一遍
            """
            changes = prev_tree.diff_to_tree(commit.tree)
            print("commit: ", prev_k, "=====================================")
            if True:
                patch_fname = os.path.join(target_path, prev_k+".patch")
                with open(patch_fname, 'w') as fh:
                    for c in changes:
                        c_delta = c.delta
                        b_emit_patch = False
                        # 与源文件相关 或 与修改过的文件相关
                        print(c_delta.new_file.path)
                        if has_related_file(c_delta.new_file.path, path_list) \
                            or has_related_file(c_delta.old_file.path, path_list):
                            b_emit_patch = True
                        
                        if b_emit_patch:
                            fh.write(c.text)
                            # for h in c.hunks:
                            #    # print(h.header)
                            #    pass
                            # exit(0)
                            # ()
            pass
        prev_tree = commit.tree
        prev_k = k

def apply_patches(repo_name, comments, patch_path):
    """
        将 patch 重新应用, 并额外增加之前 id 的引用信息,

        - 假定 repo 的位置是所在目录的兄弟目录
    """
    repo_realpath = os.path.join(repo_name, '.git')
    
    repo = Repository(repo_realpath)
    
    ht_comments =dict(zip(comments, comments))

    base_patch = os.path.basename(patch_path)

    cnt = 0
    prev_tree = None
    prev_k = None
    prev_message = None

    with io.StringIO() as fh:

        for commit in repo.walk(repo.head.target, GIT_SORT_TOPOLOGICAL|GIT_SORT_REVERSE):
            k = str(commit.oid)
            if prev_k and prev_k in ht_comments:
                # print(prev_message)
                patch_fname = os.path.join(base_patch, prev_k + ".patch")
                """
                FIXME: how to create image files, eg. png
                """
                fh.write("patch -p1 -i ../" + patch_fname + "\n")
                # 假定当前是 git 的仓库
                fh.write("git add . \n")
                # 处理　message
                """
                git commit -F- <<EOF
Message

goes
here
EOF
                """
                fh.write("git commit -F- <<EOF\n")
                for m in prev_message.split('\n'):
                    fh.write(m.strip()+"\n")
                fh.write("EOF\n")
                pass
            prev_tree = commit.tree
            prev_message = commit.message
            prev_k = k

        return fh.getvalue()
    

def dump_commits(repo_name):
    repo_realpath = os.path.join(repo_name, '.git')
    
    repo = Repository(repo_realpath)
    
    cnt = 0
    prev_tree = None
    for commit in repo.walk(repo.head.target, GIT_SORT_TOPOLOGICAL|GIT_SORT_REVERSE):
        """
        print(commit.message)
        print(dir(commit))
        print(commit.tree, dir(commit.tree))
        """
        # tree 是当期 commit 后的文件系统视图。
        for obj in commit.tree:
            # print(obj.id, obj.type_str, obj.name)  
            #print(obj, dir(obj))
            #print(obj.read_raw())
            pass

        # print(commit.short_id, commit.oid)

        if prev_tree:
            changes = prev_tree.diff_to_tree(commit.tree)
            for c in changes:
                """
                print(c.text)
                print(dir(c))
                print(c.delta, c.delta.status_char())
                delta = c.delta
                print(delta.new_file.path, delta.old_file.path)
                """
                pass

        #if cnt == 4:
        #    exit(0)
        cnt += 1
        prev_tree = commit.tree
    print(cnt)

if __name__ == '__main__':
    fname = sys.argv[1]
    

    base_fname = os.path.basename(fname)
    db_fname = base_fname + ".commits.json"
    target_path = ".target"
    
    if not os.path.exists(db_fname):
        comments = mark_comments(fname, ["datacollector-ui"])
        
        with open(db_fname, 'w') as fh:
            json.dump(comments, fh)
    
    with open(db_fname, 'r') as fh:
        comments = json.load(fh)

    # ensure target path exist.
    if not os.path.exists(target_path):
        os.mkdir(target_path)

    comments.reverse()
    
    if False:
        export_patches(fname, comments, target_path, ["datacollector-ui"])
    shell_code = apply_patches(fname, comments, target_path)
    print(shell_code)