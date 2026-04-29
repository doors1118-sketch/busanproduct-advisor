import paramiko
import getpass

def main():
    print("==================================================")
    print("부산 공공조달 AI 챗봇 - 파일럿 테스트 계정 설정")
    print("==================================================")
    
    # 1. 사용자로부터 ID/PW 입력받기
    pilot_user = input("사용할 파일럿 ID를 입력하세요 (예: admin): ").strip()
    if not pilot_user:
        print("오류: ID를 입력해야 합니다.")
        return
        
    pilot_pass = getpass.getpass("사용할 비밀번호를 입력하세요 (화면에 보이지 않습니다): ").strip()
    if not pilot_pass:
        print("오류: 비밀번호를 입력해야 합니다.")
        return
        
    confirm_pass = getpass.getpass("비밀번호를 다시 한 번 입력하세요: ").strip()
    if pilot_pass != confirm_pass:
        print("오류: 비밀번호가 일치하지 않습니다.")
        return

    print("\n[진행 중] NCP 서버에 접속하여 설정을 반영합니다...")
    
    # 2. 서버 접속
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # 이전 단계에서 사용한 root 접속 정보
        host = '49.50.133.160'
        username = 'root'
        pwd = 'back9900@@'
        
        ssh.connect(host, username=username, password=pwd, timeout=10)
        
        # 3. 환경변수 파일 생성
        env_content = f"""PILOT_AUTH_ENABLED=true
PILOT_AUTH_USER={pilot_user}
PILOT_AUTH_PASSWORD={pilot_pass}
PROMPT_MODE=dynamic_v1_4_4
"""
        # 파일 덮어쓰기
        ssh.exec_command(f"cat << 'EOF' > /root/e2e_workspace/pilot_auth.env\n{env_content}EOF")
        ssh.exec_command("chmod 600 /root/e2e_workspace/pilot_auth.env")
        
        # 4. 서비스 재시작
        ssh.exec_command("systemctl restart busan-advisor-pilot.service")
        
        print("\n✅ 완료되었습니다!")
        print(f"이제 '{pilot_user}' 계정으로 파일럿 접속이 가능합니다.")
        print("설정하신 ID와 비밀번호를 사무실 직원분들께 공유해 주세요.")
        
    except Exception as e:
        print(f"\n❌ 서버 접속 또는 반영 중 오류가 발생했습니다: {e}")
    finally:
        try:
            ssh.close()
        except:
            pass

if __name__ == "__main__":
    main()
