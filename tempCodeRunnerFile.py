
# @app.route('/admin/stop-vote', methods=['POST'])
# def stop_vote():
#     if not session.get('admin'):
#         return redirect(url_for('login'))

#     title = request.form['title']
#     con = get_db_connection()
#     cur = con.cursor()
#     cur.execute("UPDATE votes SET active=FALSE WHERE title=%s", (title,))
#     con.commit()
#     con.close()

#     flash(f"Voting for '{title}' stopped.")
#     return redirect(url_for('admin_dashboard'))