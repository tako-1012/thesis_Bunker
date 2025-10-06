using UnityEngine;
using Unity.Robotics.Core;
using RosMessageTypes.Nav;
using RosMessageTypes.Geometry;
using Unity.Robotics.ROSTCPConnector;
using System;
using Unity.Robotics.ROSTCPConnector.ROSGeometry;
using RosMessageTypes.Tf2;

public class PerfectMapPublisher : MonoBehaviour
{
    // Topic to publish odometry data
    public string odometryTopic = "/map";
    public string topicName = "tf";

    // Publishing rate (in Hz)
    public float publishRate = 10.0f;
    float time;
    // ROS TCP Connector instance
    private ROSConnection rosConnection;

    public Vector3<FLU> local_pose;
    public QuaternionMsg local_rot;


    private void Start()
    {
        // Create a ROS connection
        rosConnection = ROSConnection.GetOrCreateInstance();
        rosConnection.RegisterPublisher<OdometryMsg>(odometryTopic);
        rosConnection.RegisterPublisher<TFMessageMsg>(topicName);
    }

    void FixedUpdate()
        {
            time += Time.deltaTime;
            if (time<0.05f) return;
            time = 0.0f;
            local_pose=new Vector3<FLU>(0,0,0);
            // Quaternion my_quarternion = new Quaternion(0,0,0,1);
            local_rot=new QuaternionMsg(0,0,0,1);
            PublishOdometry();
            PublishTransform();
        }

    private void PublishTransform()
    {
        TFMessageMsg tfMessage = new TFMessageMsg(new TransformStampedMsg[] { CreateTransform() });
        rosConnection.Publish(topicName, tfMessage);
    }
    TransformStampedMsg CreateTransform()
    {
        // Create the odometry message
        TransformStampedMsg msg = new TransformStampedMsg{
            header = new RosMessageTypes.Std.HeaderMsg
            {
                stamp = new TimeStamp(Clock.Now),
                frame_id = "map"
            },
            transform = new TransformMsg(local_pose,local_rot),
            child_frame_id = "perfect_odom"
        };

        return msg;
    }
    private void PublishOdometry()
    {
        
        // Create the odometry message
        PoseMsg pose = new PoseMsg{
            position = local_pose,
            orientation = local_rot
            
        };

        PoseWithCovarianceMsg posewithcov = new PoseWithCovarianceMsg{
            pose = pose,
            covariance = new double[36]
        };

        
        // Create the odometry message
        OdometryMsg odometryMessage = new OdometryMsg
        {
            header = new RosMessageTypes.Std.HeaderMsg
            {
                stamp = new TimeStamp(Clock.Now),
                frame_id = "map"
            },
            pose = posewithcov,
            child_frame_id = "perfect_odom"
        };


        // Publish the odometry message to the ROS topic
        rosConnection.Publish(odometryTopic, odometryMessage);
    }
  
}